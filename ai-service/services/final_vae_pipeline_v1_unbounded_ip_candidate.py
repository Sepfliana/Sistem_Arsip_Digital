"""The single active final VAE model, scoring, and inference pipeline.

All callers use the Stage 2 preprocessing contract and its train-only artifacts.
The module intentionally has no fallback to historical models or preprocessors.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from utils.final_preprocessing_contract import FEATURE_COLUMNS, preprocess_for_inference


SERVICE_DIR = Path(__file__).resolve().parents[1]
SSOT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
PREPROCESSING_DIR = SSOT_DIR / "preprocessing_stage2"
FINAL_MODEL_DIR = SERVICE_DIR / "models" / "final_vae"
MODEL_PATH = FINAL_MODEL_DIR / "vae_model_final.pth"
MODEL_CONFIG_PATH = FINAL_MODEL_DIR / "model_config.json"
MODEL_METADATA_PATH = FINAL_MODEL_DIR / "model_metadata.json"
THRESHOLD_PATH = FINAL_MODEL_DIR / "threshold.json"

MODEL_CONFIG = {
    "input_dimension": 9,
    "latent_dimension": 8,
    "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]},
    "activation": "ReLU",
    "dropout": 0.2,
    "optimizer": "Adam",
    "learning_rate": 0.001,
    "epochs": 100,
    "batch_size": 30004,
    "training_strategy": "KL capacity annealing",
    "capacity_target": 0.5,
    "capacity_warmup_epochs": 60,
    "capacity_loss_weight": 1.0,
    "inference_latent": "mu (deterministic posterior mean)",
}


class FinalVariationalAutoencoder(nn.Module):
    """Locked architecture: 9→64→32→8→32→64→9, ReLU, dropout 0.2."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(9, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
        )
        self.mu = nn.Linear(32, 8)
        self.logvar = nn.Linear(32, 8)
        self.decoder = nn.Sequential(
            nn.Linear(8, 32),
            nn.ReLU(),
            nn.Linear(32, 64),
            nn.ReLU(),
            nn.Linear(64, 9),
        )

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        encoded = self.encoder(inputs)
        mu = self.mu(encoded)
        logvar = self.logvar(encoded)
        # Reparameterisation is required while fitting the VAE.  Evaluation and
        # deployment use the posterior mean so identical input has identical
        # reconstruction error and threshold decision.
        latent = mu + torch.exp(0.5 * logvar) * torch.randn_like(mu) if self.training else mu
        return self.decoder(latent), mu, logvar


def validate_model_config(config: dict[str, Any]) -> None:
    required = {
        "input_dimension": 9,
        "latent_dimension": 8,
        "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]},
        "activation": "ReLU",
        "dropout": 0.2,
        "optimizer": "Adam",
        "learning_rate": 0.001,
        "epochs": 100,
        "capacity_target": 0.5,
        "capacity_warmup_epochs": 60,
    }
    for key, expected in required.items():
        if config.get(key) != expected:
            raise ValueError(f"Konfigurasi model final tidak sesuai {key}: {config.get(key)!r}.")


@lru_cache(maxsize=1)
def load_final_model() -> FinalVariationalAutoencoder:
    if not MODEL_PATH.exists() or not MODEL_CONFIG_PATH.exists() or not MODEL_METADATA_PATH.exists():
        raise FileNotFoundError("Artifact model final belum lengkap. Jalankan train_vae_pytorch.py final terlebih dahulu.")
    config = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    validate_model_config(config)
    metadata = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))
    if metadata.get("feature_order") != list(FEATURE_COLUMNS):
        raise ValueError("Metadata model final tidak sesuai feature order Tahap 2.")
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    model = FinalVariationalAutoencoder()
    model.load_state_dict(state_dict)
    model.eval()
    return model


@lru_cache(maxsize=1)
def load_final_threshold() -> float:
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError("Artifact threshold final belum tersedia.")
    metadata = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    if metadata.get("method") != "percentile-95 of train-normal reconstruction scores":
        raise ValueError("Metode threshold artifact final bukan P95 train normal.")
    if metadata.get("test_used") is not False:
        raise ValueError("Artifact threshold final tidak membuktikan test set tidak digunakan.")
    threshold = float(metadata["threshold"])
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError("Nilai threshold final tidak valid.")
    return threshold


def reconstruction_details(values: np.ndarray, batch_size: int = 4096) -> dict[str, np.ndarray]:
    """Return deterministic reconstruction, nine per-feature errors, and mean score."""
    inputs = np.asarray(values, dtype=np.float32)
    if inputs.ndim != 2 or inputs.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError(f"Input VAE harus berbentuk (n, 9), diterima {inputs.shape}.")
    if not np.isfinite(inputs).all():
        raise ValueError("Input VAE berisi NaN/Inf.")
    model = load_final_model()
    reconstructed_batches: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch_size):
            batch = torch.from_numpy(inputs[start : start + batch_size])
            reconstruction, _, _ = model(batch)
            reconstructed_batches.append(reconstruction.cpu().numpy())
    reconstructed = np.concatenate(reconstructed_batches, axis=0)
    feature_errors = np.square(inputs - reconstructed).astype(np.float64)
    scores = feature_errors.mean(axis=1)
    return {
        "reconstruction": reconstructed.astype(np.float32),
        "feature_errors": feature_errors,
        "anomaly_scores": scores,
    }


def build_explanation(feature_errors: np.ndarray) -> tuple[dict[str, float], dict[str, float], list[dict[str, float | str]]]:
    errors = np.asarray(feature_errors, dtype=np.float64)
    if errors.shape != (len(FEATURE_COLUMNS),):
        raise ValueError("Feature error harus berisi tepat sembilan nilai.")
    total = float(errors.sum())
    contributions = np.zeros_like(errors) if total <= 0 else errors / total
    error_map = {feature: float(value) for feature, value in zip(FEATURE_COLUMNS, errors, strict=True)}
    contribution_map = {
        feature: float(value) for feature, value in zip(FEATURE_COLUMNS, contributions, strict=True)
    }
    order = np.argsort(-contributions, kind="stable")[:3]
    dominant = [
        {
            "feature": FEATURE_COLUMNS[int(index)],
            "error": float(errors[int(index)]),
            "contribution": float(contributions[int(index)]),
        }
        for index in order
        if total > 0
    ]
    return error_map, contribution_map, dominant


def risk_level(score: float, threshold: float) -> str:
    """Operational interpretation only; never affects score or anomaly decision."""
    if score <= threshold:
        return "LOW"
    return "HIGH" if score >= threshold * 1.5 else "MEDIUM"


def predict_final(payload: Any) -> dict[str, Any]:
    """Raw audit log → Stage 2 contract → final VAE → explanation."""
    scaled = preprocess_for_inference(payload, PREPROCESSING_DIR)
    details = reconstruction_details(scaled)
    score = float(details["anomaly_scores"][0])
    threshold = load_final_threshold()
    is_anomaly = bool(score > threshold)
    errors, contributions, dominant = build_explanation(details["feature_errors"][0])
    dominant_text = ", ".join(
        f"{item['feature']} ({float(item['contribution']) * 100:.1f}%)" for item in dominant
    ) or "tidak ada error rekonstruksi"
    explanation = (
        f"Skor {score:.6f} {'melewati' if is_anomaly else 'tidak melewati'} threshold "
        f"P95 train-normal {threshold:.6f}. Kontributor dominan: {dominant_text}."
    )
    timestamp = payload.get("waktu") if isinstance(payload, dict) else payload.waktu
    return {
        "anomaly_score": score,
        "reconstruction_error": score,
        "score": score,
        "threshold": threshold,
        "risk_level": risk_level(score, threshold),
        "timestamp": str(timestamp),
        "is_anomaly": is_anomaly,
        "status": "ANOMALY" if is_anomaly else "NORMAL",
        "feature_errors": errors,
        "feature_contributions": contributions,
        "dominant_features": dominant,
        "explanation": explanation,
        "preprocessing_contract": "stage2-final-v1",
    }
