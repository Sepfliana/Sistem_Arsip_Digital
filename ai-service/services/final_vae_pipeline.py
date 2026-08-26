"""One active final VAE path: Stage 1 SSOT, Stage 2 v2 contract, final model."""

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
FEATURE_CONTRACT_PATH = PREPROCESSING_DIR / "feature_contract.json"
FINAL_MODEL_DIR = SERVICE_DIR / "models" / "final_vae"
MODEL_PATH = FINAL_MODEL_DIR / "vae_model_final.pth"
MODEL_CONFIG_PATH = FINAL_MODEL_DIR / "model_config.json"
MODEL_METADATA_PATH = FINAL_MODEL_DIR / "model_metadata.json"
THRESHOLD_PATH = FINAL_MODEL_DIR / "threshold.json"
EXPECTED_PREPROCESSING_CONTRACT = "stage2-final-v2-bounded-ip-zscore"

MODEL_CONFIG = {
    "input_dimension": 9, "latent_dimension": 8,
    "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]},
    "activation": "ReLU", "dropout": 0.2, "optimizer": "Adam", "learning_rate": 0.001,
    "epochs": 100, "batch_size": 30004, "training_strategy": "KL capacity annealing",
    "capacity_target": 0.5, "capacity_warmup_epochs": 60, "capacity_loss_weight": 1.0,
    "inference_latent": "mu (deterministic posterior mean)",
}


class FinalVariationalAutoencoder(nn.Module):
    """Locked architecture: 9 -> 64 -> 32 -> latent 8 -> 32 -> 64 -> 9."""

    def __init__(self) -> None:
        super().__init__()
        self.encoder = nn.Sequential(nn.Linear(9, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 32), nn.ReLU())
        self.mu, self.logvar = nn.Linear(32, 8), nn.Linear(32, 8)
        self.decoder = nn.Sequential(nn.Linear(8, 32), nn.ReLU(), nn.Linear(32, 64), nn.ReLU(), nn.Linear(64, 9))

    def forward(self, inputs: Tensor) -> tuple[Tensor, Tensor, Tensor]:
        hidden = self.encoder(inputs)
        mu, logvar = self.mu(hidden), self.logvar(hidden)
        latent = mu + torch.exp(0.5 * logvar) * torch.randn_like(mu) if self.training else mu
        return self.decoder(latent), mu, logvar


def validate_model_config(config: dict[str, Any]) -> None:
    expected = {"input_dimension": 9, "latent_dimension": 8, "hidden_layers": {"encoder": [64, 32], "decoder": [32, 64]}, "activation": "ReLU", "dropout": 0.2, "optimizer": "Adam", "learning_rate": 0.001, "epochs": 100, "capacity_target": 0.5, "capacity_warmup_epochs": 60}
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"Konfigurasi VAE final tidak sesuai {key}: {config.get(key)!r}.")


@lru_cache(maxsize=1)
def preprocessing_contract_version() -> str:
    if not FEATURE_CONTRACT_PATH.exists():
        raise FileNotFoundError("feature_contract Stage 2 final tidak ditemukan.")
    version = json.loads(FEATURE_CONTRACT_PATH.read_text(encoding="utf-8")).get("contract_version")
    if version != EXPECTED_PREPROCESSING_CONTRACT:
        raise ValueError(f"Kontrak preprocessing aktif bukan final v2: {version!r}.")
    return version


@lru_cache(maxsize=1)
def load_final_model() -> FinalVariationalAutoencoder:
    if not all(path.exists() for path in (MODEL_PATH, MODEL_CONFIG_PATH, MODEL_METADATA_PATH)):
        raise FileNotFoundError("Artifact model final belum lengkap; jalankan trainer final setelah Stage 2 PASS.")
    preprocessing_contract_version()
    config = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(MODEL_METADATA_PATH.read_text(encoding="utf-8"))
    validate_model_config(config)
    if metadata.get("feature_order") != list(FEATURE_COLUMNS):
        raise ValueError("Feature order artifact model tidak sama dengan kontrak Stage 2.")
    if metadata.get("preprocessing", {}).get("contract") != EXPECTED_PREPROCESSING_CONTRACT:
        raise ValueError("Artifact model tidak dipasangkan dengan kontrak preprocessing final v2.")
    checkpoint = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    model = FinalVariationalAutoencoder()
    model.load_state_dict(checkpoint.get("model_state_dict", checkpoint))
    model.eval()
    return model


@lru_cache(maxsize=1)
def load_final_threshold() -> float:
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError("Artifact threshold final belum tersedia.")
    payload = json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))
    if payload.get("method") != "percentile-95 of train-normal reconstruction scores" or payload.get("test_used") is not False:
        raise ValueError("Threshold artifact bukan P95 train-normal yang tervalidasi.")
    value = float(payload["threshold"])
    if not np.isfinite(value) or value < 0:
        raise ValueError("Threshold final tidak valid.")
    return value


def reconstruction_details(values: np.ndarray, batch_size: int = 4096) -> dict[str, np.ndarray]:
    inputs = np.asarray(values, dtype=np.float32)
    if inputs.ndim != 2 or inputs.shape[1] != len(FEATURE_COLUMNS) or not np.isfinite(inputs).all():
        raise ValueError(f"Input VAE harus finite berbentuk (n, 9), diterima {inputs.shape}.")
    model = load_final_model()
    results: list[np.ndarray] = []
    with torch.no_grad():
        for offset in range(0, len(inputs), batch_size):
            reconstruction, _, _ = model(torch.from_numpy(inputs[offset:offset + batch_size]))
            results.append(reconstruction.numpy())
    reconstruction = np.concatenate(results, axis=0)
    feature_errors = np.square(inputs - reconstruction).astype(np.float64)
    return {"reconstruction": reconstruction.astype(np.float32), "feature_errors": feature_errors, "anomaly_scores": feature_errors.mean(axis=1)}


def build_explanation(errors: np.ndarray) -> tuple[dict[str, float], dict[str, float], list[dict[str, float | str]]]:
    values = np.asarray(errors, dtype=np.float64)
    if values.shape != (9,):
        raise ValueError("Feature error harus memiliki sembilan nilai.")
    total = float(values.sum())
    contribution = np.zeros_like(values) if total <= 0 else values / total
    feature_errors = {name: float(value) for name, value in zip(FEATURE_COLUMNS, values, strict=True)}
    contributions = {name: float(value) for name, value in zip(FEATURE_COLUMNS, contribution, strict=True)}
    dominant = [{"feature": FEATURE_COLUMNS[int(index)], "error": float(values[int(index)]), "contribution": float(contribution[int(index)])} for index in np.argsort(-contribution, kind="stable")[:3] if total > 0]
    return feature_errors, contributions, dominant


def risk_level(score: float, threshold: float) -> str:
    return "LOW" if score <= threshold else ("HIGH" if score >= threshold * 1.5 else "MEDIUM")


def predict_final(payload: Any) -> dict[str, Any]:
    contract = preprocessing_contract_version()
    transformed = preprocess_for_inference(payload, PREPROCESSING_DIR)
    details = reconstruction_details(transformed)
    score, threshold = float(details["anomaly_scores"][0]), load_final_threshold()
    anomaly = bool(score > threshold)
    errors, contributions, dominant = build_explanation(details["feature_errors"][0])
    dominant_text = ", ".join(f"{item['feature']} ({float(item['contribution']) * 100:.1f}%)" for item in dominant) or "tidak ada error rekonstruksi"
    timestamp = payload.get("waktu") if isinstance(payload, dict) else payload.waktu
    return {"anomaly_score": score, "reconstruction_error": score, "score": score, "threshold": threshold, "risk_level": risk_level(score, threshold), "timestamp": str(timestamp), "is_anomaly": anomaly, "status": "ANOMALY" if anomaly else "NORMAL", "feature_errors": errors, "feature_contributions": contributions, "dominant_features": dominant, "explanation": f"Skor {score:.6f} {'melewati' if anomaly else 'tidak melewati'} threshold P95 train-normal {threshold:.6f}. Kontributor dominan: {dominant_text}.", "preprocessing_contract": contract}
