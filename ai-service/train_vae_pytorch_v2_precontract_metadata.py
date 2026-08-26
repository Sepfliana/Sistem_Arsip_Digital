"""Train the one final VAE from Stage 1 SSOT and Stage 2 matrices only."""

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


def set_deterministic_seed() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    try:
        torch.use_deterministic_algorithms(True)
    except RuntimeError:
        pass


def capacity(epoch: int) -> float:
    return float(MODEL_CONFIG["capacity_target"] * min(epoch / MODEL_CONFIG["capacity_warmup_epochs"], 1.0))


def losses(model: FinalVariationalAutoencoder, inputs: torch.Tensor, epoch: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    reconstruction, mu, logvar = model(inputs)
    reconstruction_loss = functional.mse_loss(reconstruction, inputs, reduction="mean")
    kl_loss = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
    return reconstruction_loss + torch.abs(kl_loss - capacity(epoch)), reconstruction_loss, kl_loss


def load_data() -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame]]:
    stage2 = json.loads(STAGE2_VALIDATION_PATH.read_text(encoding="utf-8"))
    if not str(stage2.get("status", "")).endswith("PASS"):
        raise ValueError("Tahap 2 belum PASS; retraining final dihentikan.")
    matrices: dict[str, np.ndarray] = {}
    frames: dict[str, pd.DataFrame] = {}
    for split, expected in EXPECTED_ROWS.items():
        matrix = np.load(PREPROCESSING_DIR / f"X_{split}_final.npy", allow_pickle=False)
        frame = pd.read_csv(SSOT_DIR / f"{split}_metadata.csv", encoding="utf-8")
        if matrix.shape != (expected, len(FEATURE_COLUMNS)) or matrix.dtype != np.float32:
            raise ValueError(f"Matrix {split} bukan Stage 2 final: {matrix.shape}/{matrix.dtype}.")
        if not np.isfinite(matrix).all() or len(frame) != len(matrix):
            raise ValueError(f"Matrix/metadata {split} tidak finite atau tidak sejajar.")
        matrices[split], frames[split] = matrix, frame
    if not frames["train"]["anomaly_type"].eq("Normal").all():
        raise ValueError("Train SSOT mengandung anomaly label; fit final dibatalkan.")
    return matrices, frames


def score_metrics(scores: np.ndarray, actual_anomaly: np.ndarray, threshold: float) -> dict[str, Any]:
    predicted = scores > threshold
    tp = int((predicted & actual_anomaly).sum())
    tn = int((~predicted & ~actual_anomaly).sum())
    fp = int((predicted & ~actual_anomaly).sum())
    fn = int((~predicted & actual_anomaly).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "accuracy": float((tp + tn) / len(actual_anomaly)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if fn + tp else 0.0,
        "flag_rate": float(predicted.mean()),
        "actual_anomaly_rate": float(actual_anomaly.mean()),
    }


def distribution(scores: np.ndarray, errors: np.ndarray) -> dict[str, Any]:
    if len(scores) == 0:
        return {"n": 0}
    average_errors = errors.mean(axis=0)
    contribution_total = float(average_errors.sum())
    contributions = np.zeros_like(average_errors) if contribution_total <= 0 else average_errors / contribution_total
    return {
        "n": int(len(scores)),
        "score": {
            "min": float(scores.min()), "max": float(scores.max()), "mean": float(scores.mean()),
            "median": float(np.median(scores)), "std": float(scores.std()), "p95": float(np.percentile(scores, 95)),
        },
        "mean_feature_errors": {key: float(value) for key, value in zip(FEATURE_COLUMNS, average_errors, strict=True)},
        "mean_feature_contributions": {key: float(value) for key, value in zip(FEATURE_COLUMNS, contributions, strict=True)},
        "dominant_feature": FEATURE_COLUMNS[int(np.argmax(contributions))],
    }


def evaluate(matrices: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], threshold: float) -> dict[str, Any]:
    from services import final_vae_pipeline

    final_vae_pipeline.load_final_model.cache_clear()
    details = {name: reconstruction_details(matrix) for name, matrix in matrices.items()}
    report: dict[str, Any] = {"threshold": threshold, "train_normal": distribution(details["train"]["anomaly_scores"], details["train"]["feature_errors"]), "splits": {}}
    for split in ("validation", "test"):
        frame = frames[split]
        scores, errors = details[split]["anomaly_scores"], details[split]["feature_errors"]
        actual = frame["anomaly_type"].ne("Normal").to_numpy(dtype=bool)
        worktime = frame["timestamp"].map(lambda value: 8 <= pd.Timestamp(value).hour <= 15).to_numpy(dtype=bool)
        localhost = frame["ip_address"].astype(str).str.strip().isin(["127.0.0.1", "::1", "::ffff:127.0.0.1"]).to_numpy(dtype=bool)
        activities: dict[str, Any] = {}
        for activity in sorted(frame["activity"].astype(str).unique()):
            mask = frame["activity"].astype(str).eq(activity).to_numpy(dtype=bool)
            activities[activity] = {
                "n": int(mask.sum()), "score_mean": float(scores[mask].mean()),
                "flag_rate": float((scores[mask] > threshold).mean()), "anomaly_rate": float(actual[mask].mean()),
            }
        report["splits"][split] = {
            "metrics": score_metrics(scores, actual, threshold),
            "distribution_all": distribution(scores, errors),
            "distribution_normal": distribution(scores[~actual], errors[~actual]),
            "distribution_anomaly": distribution(scores[actual], errors[actual]),
            "time_breakdown": {
                "working_hours_08_15": distribution(scores[worktime], errors[worktime]),
                "outside_working_hours": distribution(scores[~worktime], errors[~worktime]),
            },
            "ip_breakdown": {
                "localhost_loopback": distribution(scores[localhost], errors[localhost]),
                "non_localhost": distribution(scores[~localhost], errors[~localhost]),
                "localhost_rows_present": int(localhost.sum()),
            },
            "activity_breakdown": activities,
        }
    return report


def write_final_metadata(matrices: dict[str, np.ndarray], evaluation: dict[str, Any], history: list[dict[str, float | int]]) -> None:
    preprocessing_paths = [PREPROCESSING_DIR / item for item in ("categorical_encoder.pkl", "train_only_scaler.pkl", "feature_contract.json", "artifact_manifest.json")]
    metadata = {
        "status": "TRAINED_AND_EVALUATED_PENDING_FINAL_AUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_order": list(FEATURE_COLUMNS), "architecture": MODEL_CONFIG,
        "seed": {"python": SEED, "numpy": SEED, "torch": SEED},
        "training": {"train_rows": int(len(matrices["train"])), "train_anomaly_rows": 0, "epochs_run": len(history), "validation_and_test_not_used_for_fitting": True},
        "threshold": {"method": "P95 train normal", "path": str(THRESHOLD_PATH), "value": evaluation["threshold"]},
        "preprocessing": {"contract": "stage2-final-v1", "artifact_dir": str(PREPROCESSING_DIR), "artifacts_sha256": {path.name: sha256_of(path) for path in preprocessing_paths}},
        "artifacts_sha256": {name: sha256_of(path) for name, path in {"model": MODEL_PATH, "config": MODEL_CONFIG_PATH, "threshold": THRESHOLD_PATH, "history": HISTORY_PATH, "evaluation": EVALUATION_PATH, "training_metadata": TRAINING_METADATA_PATH}.items()},
        "runtime": {"torch": torch.__version__, "python": platform.python_version(), "device": "cpu"},
    }
    MODEL_METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    validate_model_config(MODEL_CONFIG)
    set_deterministic_seed()
    matrices, frames = load_data()
    model = FinalVariationalAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=MODEL_CONFIG["learning_rate"])
    loader = DataLoader(TensorDataset(torch.from_numpy(matrices["train"])), batch_size=min(int(MODEL_CONFIG["batch_size"]), len(matrices["train"])), shuffle=True, generator=torch.Generator().manual_seed(SEED))
    validation_normal = matrices["validation"][frames["validation"]["anomaly_type"].eq("Normal").to_numpy(dtype=bool)]
    history: list[dict[str, float | int]] = []
    for epoch in range(1, int(MODEL_CONFIG["epochs"]) + 1):
        model.train()
        total_sum = reconstruction_sum = kl_sum = 0.0
        rows = 0
        for (batch,) in loader:
            optimizer.zero_grad()
            total, reconstruction, kl = losses(model, batch, epoch)
            total.backward(); optimizer.step()
            size = batch.size(0); rows += size
            total_sum += float(total.item()) * size; reconstruction_sum += float(reconstruction.item()) * size; kl_sum += float(kl.item()) * size
        model.eval()
        with torch.no_grad():
            validation_total, validation_reconstruction, validation_kl = losses(model, torch.from_numpy(validation_normal), epoch)
        history.append({"epoch": epoch, "train_loss": total_sum / rows, "train_reconstruction_loss": reconstruction_sum / rows, "train_kl_loss": kl_sum / rows, "validation_normal_loss": float(validation_total), "validation_normal_reconstruction_loss": float(validation_reconstruction), "validation_normal_kl_loss": float(validation_kl), "kl_capacity": capacity(epoch)})

    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.eval()
    torch.save({"model_state_dict": model.state_dict(), "config": MODEL_CONFIG, "seed": SEED, "epochs_completed": len(history)}, MODEL_PATH)
    MODEL_CONFIG_PATH.write_text(json.dumps(MODEL_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    with torch.no_grad():
        source = torch.from_numpy(matrices["train"])
        reconstruction, _, _ = model(source)
        train_errors = np.square(source.numpy() - reconstruction.numpy()).astype(np.float64)
    train_scores = train_errors.mean(axis=1)
    threshold = float(np.percentile(train_scores, 95))
    THRESHOLD_PATH.write_text(json.dumps({"method": "percentile-95 of train-normal reconstruction scores", "threshold": threshold, "fit_split": "train", "train_rows": int(len(train_scores)), "train_anomaly_rows": 0, "validation_used_for_threshold": False, "test_used": False, "mean_plus_3std_reference_not_selected": float(train_scores.mean() + 3 * train_scores.std()), "selection_rationale": "P95 train reconstruction score is the locked existing-production method reaffirmed by the Stage 11 forensic decision."}, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    TRAINING_METADATA_PATH.write_text(json.dumps({"train_ssot_rows": int(len(matrices["train"])), "train_anomaly_rows": 0, "validation_rows": int(len(matrices["validation"])), "test_rows": int(len(matrices["test"])), "epochs_completed": len(history), "validation_and_test_fitting": False, "seed": SEED}, ensure_ascii=False, indent=2), encoding="utf-8")
    MODEL_METADATA_PATH.write_text(json.dumps({"status": "TRAINED_PENDING_EVALUATION", "feature_order": list(FEATURE_COLUMNS), "architecture": MODEL_CONFIG}, ensure_ascii=False, indent=2), encoding="utf-8")
    evaluation = evaluate(matrices, frames, threshold)
    EVALUATION_PATH.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    write_final_metadata(matrices, evaluation, history)
    print(json.dumps({"status": "TRAINED", "threshold": threshold, "test_metrics": evaluation["splits"]["test"]["metrics"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
