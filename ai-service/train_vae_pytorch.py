"""Train the one final VAE after the Stage 2 v2 contract passes.

Only Stage 1 train-normal matrix is fitted. Validation and test are isolated
from fitting and threshold calculation; test is read only for final reporting.
"""

from __future__ import annotations

import hashlib
import json
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch.nn import functional as functional
from torch.utils.data import DataLoader, TensorDataset

from services.final_vae_pipeline import (
    EXPECTED_PREPROCESSING_CONTRACT,
    FINAL_MODEL_DIR,
    MODEL_CONFIG,
    MODEL_CONFIG_PATH,
    MODEL_METADATA_PATH,
    MODEL_PATH,
    PREPROCESSING_DIR,
    THRESHOLD_PATH,
    FinalVariationalAutoencoder,
    reconstruction_details,
    validate_model_config,
)
from utils.final_preprocessing_contract import FEATURE_COLUMNS


SERVICE_DIR = Path(__file__).resolve().parent
SSOT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
HISTORY_PATH = FINAL_MODEL_DIR / "training_history.json"
EVALUATION_PATH = FINAL_MODEL_DIR / "evaluation.json"
TRAINING_METADATA_PATH = FINAL_MODEL_DIR / "training_metadata.json"
STAGE2_VALIDATION_PATH = PREPROCESSING_DIR / "validation_results.json"
SEED = 42
EXPECTED_ROWS = {"train": 6692, "validation": 4168, "test": 4140}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_everything() -> None:
    random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED); torch.set_num_threads(4)
    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        pass


def kl_capacity(epoch: int) -> float:
    return float(MODEL_CONFIG["capacity_target"] * min(epoch / MODEL_CONFIG["capacity_warmup_epochs"], 1.0))


def loss_parts(model: FinalVariationalAutoencoder, batch: torch.Tensor, epoch: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    reconstruction, mu, logvar = model(batch)
    reconstruction_loss = functional.mse_loss(reconstruction, batch, reduction="mean")
    kl_loss = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
    return reconstruction_loss + torch.abs(kl_loss - kl_capacity(epoch)), reconstruction_loss, kl_loss


def load_data() -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame]]:
    stage2 = json.loads(STAGE2_VALIDATION_PATH.read_text(encoding="utf-8"))
    if stage2.get("status") != "STAGE 2 — PASS" or stage2.get("contract_version") != EXPECTED_PREPROCESSING_CONTRACT:
        raise ValueError("Artifact preprocessing final v2 belum PASS; retraining dilarang.")
    matrices: dict[str, np.ndarray] = {}
    frames: dict[str, pd.DataFrame] = {}
    for split, expected in EXPECTED_ROWS.items():
        matrix = np.load(PREPROCESSING_DIR / f"X_{split}_final.npy", allow_pickle=False)
        frame = pd.read_csv(SSOT_DIR / f"{split}_metadata.csv", encoding="utf-8")
        if matrix.shape != (expected, 9) or matrix.dtype != np.float32 or len(frame) != expected or not np.isfinite(matrix).all():
            raise ValueError(f"Matrix/metadata {split} bukan SSOT Stage 2 final yang valid.")
        matrices[split], frames[split] = matrix, frame
    if not frames["train"]["anomaly_type"].eq("Normal").all():
        raise ValueError("Training final tercampur label anomali.")
    return matrices, frames


def metric(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = scores > threshold
    tp, tn = int((predicted & labels).sum()), int((~predicted & ~labels).sum())
    fp, fn = int((predicted & ~labels).sum()), int((~predicted & labels).sum())
    precision, recall = (tp / (tp + fp) if tp + fp else 0.0), (tp / (tp + fn) if tp + fn else 0.0)
    return {"confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp}, "accuracy": float((tp + tn) / len(labels)), "precision": float(precision), "recall": float(recall), "f1": float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0, "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0, "false_negative_rate": float(fn / (fn + tp)) if fn + tp else 0.0, "flag_rate": float(predicted.mean()), "actual_anomaly_rate": float(labels.mean())}


def distribution(scores: np.ndarray, errors: np.ndarray) -> dict[str, Any]:
    if not len(scores):
        return {"n": 0}
    mean_errors = errors.mean(axis=0)
    total = float(mean_errors.sum())
    contributions = np.zeros_like(mean_errors) if total <= 0 else mean_errors / total
    return {"n": int(len(scores)), "score": {"min": float(scores.min()), "max": float(scores.max()), "mean": float(scores.mean()), "median": float(np.median(scores)), "std": float(scores.std()), "p95": float(np.percentile(scores, 95))}, "mean_feature_errors": {name: float(value) for name, value in zip(FEATURE_COLUMNS, mean_errors, strict=True)}, "mean_feature_contributions": {name: float(value) for name, value in zip(FEATURE_COLUMNS, contributions, strict=True)}, "dominant_feature": FEATURE_COLUMNS[int(np.argmax(contributions))]}


def evaluate(matrices: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], threshold: float) -> dict[str, Any]:
    from services import final_vae_pipeline

    final_vae_pipeline.load_final_model.cache_clear()
    details = {split: reconstruction_details(matrix) for split, matrix in matrices.items()}
    result: dict[str, Any] = {"threshold": threshold, "train_normal": distribution(details["train"]["anomaly_scores"], details["train"]["feature_errors"]), "splits": {}}
    for split in ("validation", "test"):
        frame = frames[split]
        scores, errors = details[split]["anomaly_scores"], details[split]["feature_errors"]
        anomaly = frame["anomaly_type"].ne("Normal").to_numpy(dtype=bool)
        worktime = frame["timestamp"].map(lambda value: 8 <= pd.Timestamp(value).hour <= 15).to_numpy(dtype=bool)
        loopback = frame["ip_address"].astype(str).str.strip().isin(["127.0.0.1", "::1", "::ffff:127.0.0.1"]).to_numpy(dtype=bool)
        activity: dict[str, Any] = {}
        for value in sorted(frame["activity"].astype(str).unique()):
            rows = frame["activity"].astype(str).eq(value).to_numpy(dtype=bool)
            activity[value] = {"n": int(rows.sum()), "score_mean": float(scores[rows].mean()), "flag_rate": float((scores[rows] > threshold).mean()), "anomaly_rate": float(anomaly[rows].mean())}
        result["splits"][split] = {"metrics": metric(scores, anomaly, threshold), "distribution_all": distribution(scores, errors), "distribution_normal": distribution(scores[~anomaly], errors[~anomaly]), "distribution_anomaly": distribution(scores[anomaly], errors[anomaly]), "time_breakdown": {"working_hours_08_15": distribution(scores[worktime], errors[worktime]), "outside_working_hours": distribution(scores[~worktime], errors[~worktime])}, "ip_breakdown": {"localhost_loopback": distribution(scores[loopback], errors[loopback]), "non_localhost": distribution(scores[~loopback], errors[~loopback]), "localhost_rows_present": int(loopback.sum())}, "activity_breakdown": activity}
    return result


def main() -> int:
    validate_model_config(MODEL_CONFIG)
    seed_everything()
    matrices, frames = load_data()
    model = FinalVariationalAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=MODEL_CONFIG["learning_rate"])
    loader = DataLoader(TensorDataset(torch.from_numpy(matrices["train"])), batch_size=min(int(MODEL_CONFIG["batch_size"]), len(matrices["train"])), shuffle=True, generator=torch.Generator().manual_seed(SEED))
    validation_normal = matrices["validation"][frames["validation"]["anomaly_type"].eq("Normal").to_numpy(dtype=bool)]
    history: list[dict[str, float | int]] = []
    for epoch in range(1, int(MODEL_CONFIG["epochs"]) + 1):
        model.train(); total_sum = recon_sum = kl_sum = 0.0; rows = 0
        for (batch,) in loader:
            optimizer.zero_grad(); total, reconstruction, kl = loss_parts(model, batch, epoch); total.backward(); optimizer.step()
            size = batch.size(0); rows += size; total_sum += float(total) * size; recon_sum += float(reconstruction) * size; kl_sum += float(kl) * size
        model.eval()
        with torch.no_grad():
            validation_total, validation_reconstruction, validation_kl = loss_parts(model, torch.from_numpy(validation_normal), epoch)
        history.append({"epoch": epoch, "train_loss": total_sum / rows, "train_reconstruction_loss": recon_sum / rows, "train_kl_loss": kl_sum / rows, "validation_normal_loss": float(validation_total), "validation_normal_reconstruction_loss": float(validation_reconstruction), "validation_normal_kl_loss": float(validation_kl), "kl_capacity": kl_capacity(epoch)})

    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.save({"model_state_dict": model.state_dict(), "config": MODEL_CONFIG, "seed": SEED, "epochs_completed": len(history)}, MODEL_PATH)
    MODEL_CONFIG_PATH.write_text(json.dumps(MODEL_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    with torch.no_grad():
        batch = torch.from_numpy(matrices["train"]); reconstruction, _, _ = model(batch)
        train_feature_errors = np.square(batch.numpy() - reconstruction.numpy()).astype(np.float64)
    train_scores = train_feature_errors.mean(axis=1)
    threshold = float(np.percentile(train_scores, 95))
    THRESHOLD_PATH.write_text(json.dumps({"method": "percentile-95 of train-normal reconstruction scores", "threshold": threshold, "fit_split": "train", "train_rows": len(train_scores), "train_anomaly_rows": 0, "validation_used_for_threshold": False, "test_used": False, "mean_plus_3std_reference_not_selected": float(train_scores.mean() + 3 * train_scores.std()), "selection_rationale": "P95 train reconstruction score is the locked forensic ground-truth method; mean + 3 standard deviations is recorded only as a conflicting-document reference."}, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    TRAINING_METADATA_PATH.write_text(json.dumps({"train_ssot_rows": len(matrices["train"]), "train_anomaly_rows": 0, "validation_rows": len(matrices["validation"]), "test_rows": len(matrices["test"]), "epochs_completed": len(history), "validation_and_test_fitting": False, "seed": SEED}, ensure_ascii=False, indent=2), encoding="utf-8")
    MODEL_METADATA_PATH.write_text(json.dumps({"status": "TRAINED_PENDING_EVALUATION", "feature_order": list(FEATURE_COLUMNS), "architecture": MODEL_CONFIG, "preprocessing": {"contract": EXPECTED_PREPROCESSING_CONTRACT}}, ensure_ascii=False, indent=2), encoding="utf-8")
    evaluation = evaluate(matrices, frames, threshold)
    EVALUATION_PATH.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    paired = [PREPROCESSING_DIR / name for name in ("categorical_encoder.pkl", "train_only_scaler.pkl", "feature_contract.json", "artifact_manifest.json")]
    metadata = {"status": "TRAINED_AND_EVALUATED_PENDING_FINAL_AUDIT", "created_at": datetime.now(timezone.utc).isoformat(), "feature_order": list(FEATURE_COLUMNS), "architecture": MODEL_CONFIG, "parameter_count": int(sum(item.numel() for item in model.parameters())), "seed": {"python": SEED, "numpy": SEED, "torch": SEED}, "training": {"train_rows": len(matrices["train"]), "train_anomaly_rows": 0, "epochs_run": len(history), "validation_and_test_not_used_for_fitting": True}, "threshold": {"method": "P95 train normal", "path": str(THRESHOLD_PATH), "value": threshold}, "preprocessing": {"contract": EXPECTED_PREPROCESSING_CONTRACT, "artifact_dir": str(PREPROCESSING_DIR), "artifacts_sha256": {path.name: sha256_of(path) for path in paired}}, "artifacts_sha256": {name: sha256_of(path) for name, path in {"model": MODEL_PATH, "config": MODEL_CONFIG_PATH, "threshold": THRESHOLD_PATH, "history": HISTORY_PATH, "evaluation": EVALUATION_PATH, "training_metadata": TRAINING_METADATA_PATH}.items()}, "runtime": {"torch": torch.__version__, "python": platform.python_version(), "device": "cpu"}}
    MODEL_METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "TRAINED", "contract": EXPECTED_PREPROCESSING_CONTRACT, "threshold": threshold, "test_metrics": evaluation["splits"]["test"]["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
