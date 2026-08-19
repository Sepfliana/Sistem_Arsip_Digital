"""
Stage 8 Inference Pipeline
===========================
Frozen artifact for production use.
Loads V8.1 trained model and runs anomaly detection.

Usage:
    from inference_pipeline import AnomalyDetector
    detector = AnomalyDetector()
    result = detector.predict(log_entry)
"""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
import torch

# ── Paths ───────────────────────────────────────────────────────────────────
ARTIFACTS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ARTIFACTS_DIR / "model_config.json"

# ── Preprocessing Constants ────────────────────────────────────────────────
V6_ACTIVITY_CLASSES = [
    "Administrasi", "Akses Berkas", "Kelola Berkas",
    "Kelola Perkara", "Kelola User", "Login", "Logout", "UNKNOWN",
]
V6_STATUS_CLASSES = ["Berhasil", "Gagal", "UNKNOWN"]
V6_DEVICE_CLASSES = [
    "Android", "Linux", "MacOS", "PC Windows",
    "Unknown Device", "Virtual Machine", "iOS",
]
V6_IP_CLASSES = ["External", "Internal"]
_ACTIVITY_REDUCTION = {
    "Keamanan & 2FA": "Administrasi",
    "Kelola Sarana": "Administrasi",
    "Peminjaman": "Administrasi",
    "Verifikasi": "Administrasi",
}


# ── VAE Architecture ──────────────────────────────────────────────────────
class VariationalAutoencoder(torch.nn.Module):
    """VAE: 9 -> 64 -> 32 -> 8(mu,logvar) -> 32 -> 64 -> 9"""

    def __init__(self):
        super().__init__()
        self.encoder = torch.nn.Sequential(
            torch.nn.Linear(9, 64), torch.nn.ReLU(), torch.nn.Dropout(0.2),
            torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        )
        self.mu = torch.nn.Linear(32, 8)
        self.logvar = torch.nn.Linear(32, 8)
        self.decoder = torch.nn.Sequential(
            torch.nn.Linear(8, 32), torch.nn.ReLU(),
            torch.nn.Linear(32, 64), torch.nn.ReLU(),
            torch.nn.Linear(64, 9),
        )

    def encode(self, x):
        h = self.encoder(x)
        return self.mu(h), self.logvar(h)

    def reparameterize(self, mu, logvar):
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def decode(self, z):
        return self.decoder(z)

    def forward(self, x):
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        return self.decode(z), mu, logvar


# ── AnomalyDetector Class ────────────────────────────────────────────────
class AnomalyDetector:
    """Production-ready anomaly detector using V8.1 trained VAE."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or CONFIG_PATH
        self.config = self._load_config()
        self.threshold = self.config["threshold"]["value"]
        self.device = torch.device("cpu")
        self.model = self._load_model()

    def _load_config(self) -> dict:
        with open(self.config_path, encoding="utf-8") as f:
            return json.load(f)

    def _load_model(self) -> VariationalAutoencoder:
        model = VariationalAutoencoder().to(self.device)
        # Load checkpoint from experiment directory
        checkpoint_path = ARTIFACTS_DIR.parent / "experiment_v6_final" / "retraining" / "vae_model_v8_1_experiment.pth"
        if checkpoint_path.exists():
            model.load_state_dict(torch.load(checkpoint_path, map_location=self.device, weights_only=False))
        else:
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        model.eval()
        return model

    def preprocess(self, raw_data: Dict) -> np.ndarray:
        """Apply V6 preprocessing to raw log entry."""
        df = pd.DataFrame([raw_data])
        return self._preprocess_dataframe(df)

    def _preprocess_dataframe(self, df: pd.DataFrame) -> np.ndarray:
        """Vectorized V6 preprocessing."""
        c = pd.DataFrame()

        # user_id
        c["user_id"] = pd.to_numeric(df.get("user_id", 1), errors="coerce").fillna(1.0)

        # activity
        raw_act = df.get("aksi", df.get("activity", "")).fillna("").astype(str).str.strip()
        reduced = raw_act.map(_ACTIVITY_REDUCTION)
        c["activity"] = reduced.fillna(raw_act.where(raw_act.isin(V6_ACTIVITY_CLASSES), "UNKNOWN"))

        # status (with fallback)
        status_fallback = self.config["preprocessing"]["encoders"]["status"]["fallback"]
        raw_st = df.get("status", "").fillna("").astype(str).str.strip()
        c["status"] = raw_st.where(raw_st.isin(V6_STATUS_CLASSES), status_fallback)

        # device
        device_fallback = self.config["preprocessing"]["encoders"]["device"]["fallback"]
        raw_dev = df.get("device", "").fillna("").astype(str).str.strip()
        mapped_dev = raw_dev.where(raw_dev.isin(V6_DEVICE_CLASSES), "Unknown Device")
        c["device"] = mapped_dev.replace("Unknown Device", device_fallback)

        # ip_address -> Internal/External
        ip_raw = df.get("ip_address", "").fillna("").astype(str).str.strip().str.lower()
        is_internal = (
            ip_raw.isin(["127.0.0.1", "::1", "localhost", "0.0.0.0"])
            | ip_raw.str.startswith("192.168.")
            | ip_raw.str.startswith("10.")
        )
        starts_172 = ip_raw.str.startswith("172.")
        octets = ip_raw.str.split(".", expand=True)
        _172_mask = starts_172
        if octets.shape[1] > 1:
            try:
                oct2 = pd.to_numeric(octets[1], errors="coerce").fillna(0).astype(int)
                _172_mask = starts_172 & (oct2 >= 16) & (oct2 <= 31)
            except Exception:
                pass
        is_internal = is_internal | _172_mask
        ip_stripped = ip_raw.str.replace("::ffff:", "", regex=False)
        is_internal = is_internal | (ip_stripped.str.startswith("127.") & ~is_internal)
        c["ip_address"] = np.where(is_internal, "Internal", "External")

        # duration_ms -> has_telemetry
        dur = pd.to_numeric(df.get("durasi_ms", df.get("duration_ms", 0)), errors="coerce").fillna(0.0)
        c["duration_ms"] = (dur > 0).astype(float)

        # object_count -> log1p
        obj = pd.to_numeric(df.get("jumlah_objek", df.get("object_count", 0)), errors="coerce").fillna(0.0)
        obj = obj.clip(lower=0)
        c["object_count"] = np.log1p(obj)

        # hour -> time period
        waktu_col = df.get("waktu", pd.Series([""] * len(df)))
        dt = pd.to_datetime(waktu_col, errors="coerce", utc=True)
        try:
            dt = dt.dt.tz_convert("Asia/Jakarta")
        except TypeError:
            dt = dt.dt.tz_localize("UTC").dt.tz_convert("Asia/Jakarta")
        hours_raw = dt.dt.hour.fillna(0).astype(int)
        c["hour"] = pd.cut(hours_raw, bins=[-1, 5, 11, 17, 23], labels=[3, 0, 1, 2]).astype(int)

        # day_of_week
        c["day_of_week"] = dt.dt.dayofweek.fillna(0).astype(int)

        # Encode categorical features
        encoded_cols = []
        encoder_map = {
            "activity": V6_ACTIVITY_CLASSES,
            "status": V6_STATUS_CLASSES,
            "device": V6_DEVICE_CLASSES,
            "ip_address": V6_IP_CLASSES,
        }
        for feat, classes in encoder_map.items():
            col = c[feat].copy()
            known = set(classes)
            col = col.where(col.isin(known), classes[0])
            encoded_cols.append(col.map({cls: i for i, cls in enumerate(classes)}).astype(float).values)

        # Stack features
        X = np.column_stack([
            c["user_id"].astype(float).values,
            *encoded_cols,
            c["duration_ms"].astype(float).values,
            c["object_count"].astype(float).values,
            c["hour"].astype(float).values,
            c["day_of_week"].astype(float).values,
        ])

        # Scale
        scaler = self.config["preprocessing"]["scaler"]
        mean = np.array(scaler["mean"])
        scale = np.array(scaler["scale"])
        return ((X - mean) / scale).astype("float32")

    def compute_mse(self, X: np.ndarray) -> np.ndarray:
        """Compute reconstruction error (MSE) for input features."""
        with torch.no_grad():
            x = torch.from_numpy(X).float().to(self.device)
            encoded = self.model.encoder(x)
            mu = self.model.mu(encoded)
            recon = self.model.decode(mu)
            return (x - recon).pow(2).mean(dim=1).cpu().numpy()

    def predict(self, raw_data: Dict) -> Dict:
        """Run anomaly detection on a single log entry.

        Args:
            raw_data: Dictionary with log fields (user_id, aksi, status, device, etc.)

        Returns:
            Dictionary with:
                - mse: reconstruction error
                - threshold: anomaly threshold
                - is_anomaly: bool
                - confidence: 0-1
                - risk_level: LOW/MEDIUM/HIGH
        """
        X = self.preprocess(raw_data)
        mse = self.compute_mse(X)[0]

        is_anomaly = mse >= self.threshold
        confidence = min(mse / self.threshold, 1.0) if is_anomaly else 1.0 - (mse / self.threshold)

        if mse >= self.threshold * 2:
            risk_level = "HIGH"
        elif mse >= self.threshold:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "mse": float(mse),
            "threshold": float(self.threshold),
            "is_anomaly": bool(is_anomaly),
            "confidence": float(confidence),
            "risk_level": risk_level,
        }

    def predict_batch(self, raw_data_list: list) -> list:
        """Run anomaly detection on multiple log entries."""
        return [self.predict(d) for d in raw_data_list]


# ── CLI Entry Point ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Test with sample data
    sample_normal = {
        "user_id": 1,
        "aksi": "Login",
        "status": "Berhasil",
        "device": "PC Windows",
        "ip_address": "192.168.1.100",
        "durasi_ms": 2500,
        "jumlah_objek": 1,
        "waktu": "2026-08-19T10:00:00+07:00",
    }

    sample_anomaly = {
        "user_id": 1,
        "aksi": "Login",
        "status": "Gagal",
        "device": "Virtual Machine",
        "ip_address": "8.8.8.8",
        "durasi_ms": 0,
        "jumlah_objek": 1,
        "waktu": "2026-08-19T03:00:00+07:00",
    }

    sample_localhost = {
        "user_id": 1,
        "aksi": "Login",
        "status": "UNKNOWN",
        "device": "PC Windows",
        "ip_address": "127.0.0.1",
        "durasi_ms": 0,
        "jumlah_objek": 0,
        "waktu": "2026-08-19T10:00:00+07:00",
    }

    print("Loading model...")
    detector = AnomalyDetector()

    print("\n--- Sample 1: Normal Activity ---")
    result = detector.predict(sample_normal)
    print(f"MSE: {result['mse']:.6f} | Anomaly: {result['is_anomaly']} | Risk: {result['risk_level']}")

    print("\n--- Sample 2: Anomalous Activity ---")
    result = detector.predict(sample_anomaly)
    print(f"MSE: {result['mse']:.6f} | Anomaly: {result['is_anomaly']} | Risk: {result['risk_level']}")

    print("\n--- Sample 3: Localhost Activity ---")
    result = detector.predict(sample_localhost)
    print(f"MSE: {result['mse']:.6f} | Anomaly: {result['is_anomaly']} | Risk: {result['risk_level']}")

    print("\nPipeline validated.")
