"""Kandidat inference path untuk model VAE hasil retraining Tahap 11.

Preprocessing identik dengan kontrak training Stage 9-10:
- LabelEncoder artefak training (activity/status/device), unknown -> error;
- IP -> integer 32-bit via ipaddress (IPv4 saja; invalid/IPv6 -> error);
- duration_ms / object_count mentah (tanpa log1p);
- timestamp naive lokal -> dt.hour / dt.dayofweek (Monday=0);
- scaling memakai final_train_scaler.pkl (fit TRAIN-only Stage 10).

Jalur produksi lama (services/inference.py) tidak diubah.
"""

from __future__ import annotations

import ipaddress
import json
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

SERVICE_DIR = Path(__file__).resolve().parents[1]
RETRAINED_DIR = SERVICE_DIR / "models" / "retrained"
MODEL_PATH = RETRAINED_DIR / "vae_model_stage11.pth"
THRESHOLD_PATH = RETRAINED_DIR / "stage11_threshold.json"
ENCODERS_PATH = SERVICE_DIR / "dataset" / "encoded" / "stage9_label_encoders.pkl"
SCALER_PATH = SERVICE_DIR / "dataset" / "final" / "scaler" / "final_train_scaler.pkl"

FEATURE_COLUMNS = ("user_id", "activity", "status", "device", "ip_address",
                   "duration_ms", "object_count", "hour", "day_of_week")


class _Stage11VAE(torch.nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.encoder = torch.nn.Sequential(
            torch.nn.Linear(9, 64), torch.nn.ReLU(), torch.nn.Dropout(0.2),
            torch.nn.Linear(64, 32), torch.nn.ReLU())
        self.mu = torch.nn.Linear(32, 8)
        self.logvar = torch.nn.Linear(32, 8)
        self.decoder = torch.nn.Sequential(
            torch.nn.Linear(8, 32), torch.nn.ReLU(), torch.nn.Linear(32, 64),
            torch.nn.ReLU(), torch.nn.Linear(64, 9))

    def forward(self, inputs: torch.Tensor):
        encoded = self.encoder(inputs)
        mu = self.mu(encoded)
        logvar = self.logvar(encoded)
        latent = mu + torch.exp(0.5 * logvar) * torch.randn_like(mu)
        return self.decoder(latent), mu, logvar


@lru_cache(maxsize=1)
def load_stage11_artifacts():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model kandidat tidak ditemukan: {MODEL_PATH}")
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    model = _Stage11VAE()
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    threshold = float(json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))["threshold"])
    with ENCODERS_PATH.open("rb") as file:
        encoders = pickle.load(file)
    with SCALER_PATH.open("rb") as file:
        scaler = pickle.load(file)
    return model, threshold, encoders, scaler


def _encode_category(encoders: dict, column: str, value: Any) -> int:
    encoder = encoders[column]
    text = str(value).strip()
    if text not in encoder.classes_:
        raise ValueError(
            f"Nilai '{value}' tidak ada dalam vocabulary training kolom '{column}'. "
            f"Kelas valid: {sorted(encoder.classes_)}")
    return int(encoder.transform([text])[0])


def _encode_ip(value: Any) -> int:
    try:
        parsed = ipaddress.ip_address(str(value).strip())
    except ValueError as error:
        raise ValueError(f"IP address tidak valid: '{value}'.") from error
    if parsed.version != 4:
        raise ValueError(
            f"Hanya IPv4 yang didukung kontrak training (diterima IPv{parsed.version}: "
            f"'{value}'). Tidak dipetakan ke nilai artifisial.")
    return int(parsed)


def preprocess_record_stage11(record: dict[str, Any]) -> np.ndarray:
    """Raw record -> vektor 9 fitur UNSCALED sesuai kontrak training."""
    hour_ts = pd.to_datetime(record.get("waktu", record.get("timestamp")))
    if hour_ts.tzinfo is not None:
        hour_ts = hour_ts.tz_convert("Asia/Jakarta").tz_localize(None)
    values = [
        float(int(record["user_id"])),
        _encode_category(load_stage11_artifacts()[2], "activity",
                         record.get("aksi", record.get("activity"))),
        _encode_category(load_stage11_artifacts()[2], "status", record.get("status")),
        _encode_category(load_stage11_artifacts()[2], "device", record.get("device")),
        float(_encode_ip(record.get("ip_address"))),
        float(record.get("durasi_ms", record.get("duration_ms", 0.0))),
        float(record.get("jumlah_objek", record.get("object_count", 0.0))),
        float(hour_ts.hour),
        float(hour_ts.dayofweek),
    ]
    vector = np.asarray(values, dtype=np.float64).reshape(1, -1)
    if vector.shape != (1, 9) or not np.isfinite(vector).all():
        raise ValueError("Vektor fitur tidak valid (bentuk/NaN/Inf).")
    return vector


def predict_stage11(payload: Any) -> dict[str, Any]:
    """Skor satu audit-log event memakai model kandidat Stage 11."""
    model, threshold, _, scaler = load_stage11_artifacts()
    unscaled = preprocess_record_stage11(
        payload if isinstance(payload, dict) else payload.model_dump())
    scaled = scaler.transform(unscaled).astype(np.float32)
    with torch.no_grad():
        batch = torch.from_numpy(scaled)
        reconstruction, _, _ = model(batch)
        score = float(torch.mean((batch - reconstruction).pow(2), dim=1).item())
    is_anomaly = score > threshold
    risk_level = "LOW" if not is_anomaly else ("HIGH" if score > threshold * 2 else "MEDIUM")
    waktu = payload.get("waktu") if isinstance(payload, dict) else payload.waktu
    return {
        "anomaly_score": score,
        "reconstruction_error": score,
        "score": score,
        "threshold": threshold,
        "risk_level": risk_level,
        "timestamp": str(waktu),
        "is_anomaly": is_anomaly,
        "status": "ANOMALY" if is_anomaly else "NORMAL",
    }
