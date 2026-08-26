"""VAE inference and one-time deployment threshold calculation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch

from schemas.predict_request import PredictRequest
from services.model_loader import load_model
from utils.preprocessing import preprocess_for_inference


SERVICE_DIR = Path(__file__).resolve().parents[1]
X_TRAIN_PATH = SERVICE_DIR / "dataset" / "preprocessed" / "X_train.npy"
DEPLOYMENT_CONFIG_PATH = SERVICE_DIR / "models" / "deployment_config.json"


def reconstruction_errors(values: np.ndarray, batch_size: int = 4096) -> np.ndarray:
    """Return per-row mean squared reconstruction errors from the final VAE."""
    model = load_model()
    inputs = np.asarray(values, dtype=np.float32)
    if inputs.ndim != 2 or inputs.shape[1] != 9:
        raise ValueError(f"Input VAE harus berbentuk (n, 9), didapatkan {inputs.shape}.")
    errors: list[np.ndarray] = []
    with torch.no_grad():
        for start in range(0, len(inputs), batch_size):
            batch = torch.from_numpy(inputs[start : start + batch_size])
            reconstruction, _, _ = model(batch)
            errors.append(torch.mean((batch - reconstruction).pow(2), dim=1).cpu().numpy())
    return np.concatenate(errors)


def compute_training_threshold() -> float:
    """Compute and persist the 95th-percentile threshold from X_train exactly once."""
    if not X_TRAIN_PATH.exists():
        raise FileNotFoundError(f"X_train final tidak ditemukan: {X_TRAIN_PATH}")
    training_values = np.load(X_TRAIN_PATH)
    errors = reconstruction_errors(training_values)
    threshold = float(np.percentile(errors, 95))
    DEPLOYMENT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEPLOYMENT_CONFIG_PATH.write_text(json.dumps({"threshold": threshold}, indent=2), encoding="utf-8")
    return threshold


def load_threshold() -> float:
    """Read the deployment threshold for every inference request."""
    if not DEPLOYMENT_CONFIG_PATH.exists():
        raise FileNotFoundError("deployment_config.json belum tersedia.")
    config = json.loads(DEPLOYMENT_CONFIG_PATH.read_text(encoding="utf-8"))
    threshold = float(config["threshold"])
    if not np.isfinite(threshold):
        raise ValueError("Threshold deployment tidak valid.")
    return threshold


def ensure_training_threshold() -> float:
    """Use the persisted threshold, calculating it only when absent."""
    if not DEPLOYMENT_CONFIG_PATH.exists():
        return compute_training_threshold()
    return load_threshold()


def predict(payload: PredictRequest) -> dict[str, Any]:
    """Execute preprocessing, forward pass, thresholding, and risk classification."""
    threshold = ensure_training_threshold()
    scaled_features = preprocess_for_inference(payload)
    score = float(reconstruction_errors(scaled_features)[0])
    is_anomaly = score > threshold
    risk_level = "LOW" if not is_anomaly else ("HIGH" if score > threshold * 2 else "MEDIUM")

    return {
        "anomaly_score": score,
        "reconstruction_error": score,
        "score": score,
        "threshold": threshold,
        "risk_level": risk_level,
        "timestamp": str(payload.waktu),
        "is_anomaly": is_anomaly,
        "status": "ANOMALY" if is_anomaly else "NORMAL",
    }
