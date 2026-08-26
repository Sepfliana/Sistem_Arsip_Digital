"""Train and evaluate the single final VAE pipeline from Stage 1/2 SSOT.

This replaces the former active trainer's dependency on ``dataset/preprocessed``.
It trains on Stage 1 train-normal data using the Stage 2 matrix and stores a
new final artifact without deleting any historical model artifacts.
"""

from __future__ import annotations

import copy
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
TRAINING_HISTORY_PATH = FINAL_MODEL_DIR / "training_history.json"
EVALUATION_PATH = FINAL_MODEL_DIR / "evaluation.json"
TRAINING_METADATA_PATH = FINAL_MODEL_DIR / "training_metadata.json"
PREPROCESSING_VALIDATION_PATH = PREPROCESSING_DIR / "validation_results.json"
SEED = 42


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
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


def kl_capacity(epoch: int) -> float:
    return float(MODEL_CONFIG["capacity_target"] * min(epoch / MODEL_CONFIG["capacity_warmup_epochs"], 1.0))


def vae_losses(model: FinalVariationalAutoencoder, batch: torch.Tensor, epoch: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    reconstruction, mu, logvar = model(batch)
    reconstruction_loss = functional.mse_loss(reconstruction, batch, reduction="mean")
    kl_loss = -0.5 * torch.mean(torch.sum(1 + logvar - mu.pow(2) - logvar.exp(), dim=1))
    total_loss = reconstruction_loss + MODEL_CONFIG["capacity_loss_weight"] * torch.abs(kl_loss - kl_capacity(epoch))
    return total_loss, reconstruction_loss, kl_loss


def validation_losses(model: FinalVariationalAutoencoder, values: np.ndarray, epoch: int) -> tuple[float, float, float]:
    model.eval()
    with torch.no_grad():
        batch = torch.from_numpy(values.astype(np.float32, copy=False))
        total, reconstruction, kl = vae_losses(model, batch, epoch)
    return float(total), float(reconstruction), float(kl)


def load_data() -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame]]:
    validation = json.loads(PREPROCESSING_VALIDATION_PATH.read_text(encoding="utf-8"))
    if validation.get("status") != "STAGE 2 — PASS":
        raise ValueError("Preprocessing Tahap 2 belum PASS; retraining final dilarang.")
    data: dict[str, np.ndarray] = {}
    labels: dict[str, pd.DataFrame] = {}
    expected_rows = {"train": 6692, "validation": 4168, "test": 4140}
    for split, expected in expected_rows.items():
        values = np.load(PREPROCESSING_DIR / f"X_{split}_final.npy", allow_pickle=False)
        metadata = pd.read_csv(SSOT_DIR / f"{split}_metadata.csv", encoding="utf-8")
        if values.shape != (expected, len(FEATURE_COLUMNS)) or values.dtype != np.float32:
            raise ValueError(f"Matrix {split} bukan artifact Stage 2 final yang valid: {values.shape}/{values.dtype}.")
        if not np.isfinite(values).all() or len(metadata) != len(values):
            raise ValueError(f"Matrix/metadata {split} tidak finite atau tidak aligned.")
        data[split], labels[split] = values, metadata
    if not labels["train"]["anomaly_type"].eq("Normal").all():
        raise ValueError("Train SSOT mengandung label anomali; training final dihentikan.")
    return data, labels


def metrics(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict[str, Any]:
    prediction = scores > threshold
    tp = int((prediction & labels).sum())
    tn = int((~prediction & ~labels).sum())
    fp = int((prediction & ~labels).sum())
    fn = int((~prediction & labels).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "accuracy": float((tp + tn) / len(labels)) if len(labels) else 0.0,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else 0.0,
        "false_negative_rate": float(fn / (fn + tp)) if fn + tp else 0.0,
        "flag_rate": float(prediction.mean()) if len(prediction) else 0.0,
        "actual_anomaly_rate": float(labels.mean()) if len(labels) else 0.0,
    }


def distribution(scores: np.ndarray, feature_errors: np.ndarray) -> dict[str, Any]:
    if not len(scores):
        return {"n": 0}
    mean_errors = feature_errors.mean(axis=0)
    total = float(mean_errors.sum())
    contributions = np.zeros_like(mean_errors) if total <= 0 else mean_errors / total
    return {
        "n": int(len(scores)),
        "score": {
            "min": float(scores.min()),
            "max": float(scores.max()),
            "mean": float(scores.mean()),
            "median": float(np.median(scores)),
            "std": float(scores.std()),
            "p95": float(np.percentile(scores, 95)),
        },
        "mean_feature_errors": {name: float(value) for name, value in zip(FEATURE_COLUMNS, mean_errors, strict=True)},
        "mean_feature_contributions": {name: float(value) for name, value in zip(FEATURE_COLUMNS, contributions, strict=True)},
        "dominant_feature": FEATURE_COLUMNS[int(np.argmax(contributions))],
    }


def group_distribution(scores: np.ndarray, errors: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    return distribution(scores[mask], errors[mask])


def evaluate(data: dict[str, np.ndarray], labels: dict[str, pd.DataFrame], threshold: float) -> dict[str, Any]:
    from services import final_vae_pipeline

    final_vae_pipeline.load_final_model.cache_clear()
    details = {split: reconstruction_details(values) for split, values in data.items()}
    result: dict[str, Any] = {"threshold": threshold, "splits": {}}
    for split in ("validation", "test"):
        frame = labels[split]
        scores, errors = details[split]["anomaly_scores"], details[split]["feature_errors"]
        anomaly_mask = frame["anomaly_type"].ne("Normal").to_numpy()
        working_mask = frame["timestamp"].map(lambda value: 8 <= pd.Timestamp(value).hour <= 15).to_numpy()
        localhost_mask = frame["ip_address"].astype(str).str.strip().isin(["127.0.0.1", "::1", "::ffff:127.0.0.1"]).to_numpy()
        activities: dict[str, Any] = {}
        for activity, rows in frame.groupby("activity").groups.items():
            mask = frame.index.isin(rows).to_numpy()
            activities[str(activity)] = {
                "n": int(mask.sum()),
                "score_mean": float(scores[mask].mean()),
                "flag_rate": float((scores[mask] > threshold).mean()),
                "anomaly_rate": float(anomaly_mask[mask].mean()),
            }
        result["splits"][split] = {
            "metrics": metrics(scores, anomaly_mask, threshold),
            "distribution_all": distribution(scores, errors),
            "distribution_normal": group_distribution(scores, errors, ~anomaly_mask),
            "distribution_anomaly": group_distribution(scores, errors, anomaly_mask),
            "time_breakdown": {
                "working_hours_08_15": group_distribution(scores, errors, working_mask),
                "outside_working_hours": group_distribution(scores, errors, ~working_mask),
            },
            "ip_breakdown": {
                "localhost_loopback": group_distribution(scores, errors, localhost_mask),
                "non_localhost": group_distribution(scores, errors, ~localhost_mask),
                "localhost_rows_present": int(localhost_mask.sum()),
            },
            "activity_breakdown": activities,
        }
    result["train_normal"] = distribution(details["train"]["anomaly_scores"], details["train"]["feature_errors"])
    return result


def main() -> int:
    validate_model_config(MODEL_CONFIG)
    set_deterministic_seed()
    data, labels = load_data()
    validation_normal = data["validation"][labels["validation"]["anomaly_type"].eq("Normal").to_numpy()]
    if not len(validation_normal):
        raise ValueError("Validation tidak memiliki normal row untuk monitoring model.")

    model = FinalVariationalAutoencoder()
    optimizer = torch.optim.Adam(model.parameters(), lr=MODEL_CONFIG["learning_rate"])
    loader = DataLoader(
        TensorDataset(torch.from_numpy(data["train"])),
        batch_size=min(int(MODEL_CONFIG["batch_size"]), len(data["train"])),
        shuffle=True,
        generator=torch.Generator().manual_seed(SEED),
    )
    history: list[dict[str, float | int]] = []
    best: dict[str, Any] = {"validation_loss": float("inf"), "epoch": 0, "state": None}
    for epoch in range(1, int(MODEL_CONFIG["epochs"]) + 1):
        model.train()
        total_sum = recon_sum = kl_sum = 0.0
        samples = 0
        for (batch,) in loader:
            optimizer.zero_grad()
            total, reconstruction, kl = vae_losses(model, batch, epoch)
            total.backward()
            optimizer.step()
            count = batch.size(0)
            samples += count
            total_sum += float(total.item()) * count
            recon_sum += float(reconstruction.item()) * count
            kl_sum += float(kl.item()) * count
        validation_loss, validation_recon, validation_kl = validation_losses(model, validation_normal, epoch)
        item = {
            "epoch": epoch,
            "train_loss": total_sum / samples,
            "train_reconstruction_loss": recon_sum / samples,
            "train_kl_loss": kl_sum / samples,
            "validation_normal_loss": validation_loss,
            "validation_normal_reconstruction_loss": validation_recon,
            "validation_normal_kl_loss": validation_kl,
            "kl_capacity": kl_capacity(epoch),
        }
        history.append(item)
        if validation_loss < best["validation_loss"]:
            best = {"validation_loss": validation_loss, "epoch": epoch, "state": copy.deepcopy(model.state_dict())}
    if best["state"] is None:
        raise RuntimeError("Tidak ada state model final yang terpilih.")

    FINAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model.load_state_dict(best["state"])
    model.eval()
    torch.save({"model_state_dict": best["state"], "config": MODEL_CONFIG, "best_epoch": best["epoch"], "seed": SEED}, MODEL_PATH)
    MODEL_CONFIG_PATH.write_text(json.dumps(MODEL_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")

    # The threshold is fit only to train-normal scores, before validation/test evaluation.
    with torch.no_grad():
        batch = torch.from_numpy(data["train"])
        reconstruction, _, _ = model(batch)
        train_errors = np.square(batch.numpy() - reconstruction.numpy()).astype(np.float64)
    train_scores = train_errors.mean(axis=1)
    threshold = float(np.percentile(train_scores, 95))
    THRESHOLD_PATH.write_text(
        json.dumps(
            {
                "method": "percentile-95 of train-normal reconstruction scores",
                "threshold": threshold,
                "fit_split": "train",
                "train_rows": int(len(data["train"])),
                "train_anomaly_rows": 0,
                "validation_used_for_selection": False,
                "test_used": False,
                "mean_plus_3std_reference_not_selected": float(train_scores.mean() + 3 * train_scores.std()),
                "selection_rationale": "P95 train reconstruction score is the locked existing-production method reaffirmed by the Stage 11 forensic decision.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # The evaluator verifies feature-order metadata before it loads this
    # just-written model. This minimal manifest is replaced by the complete
    # artifact manifest after evaluation and hash computation.
    MODEL_METADATA_PATH.write_text(
        json.dumps(
            {
                "status": "TRAINED_PENDING_EVALUATION",
                "feature_order": list(FEATURE_COLUMNS),
                "architecture": MODEL_CONFIG,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    from services import final_vae_pipeline

    final_vae_pipeline.load_final_model.cache_clear()
    final_vae_pipeline.load_final_threshold.cache_clear()
    evaluation = evaluate(data, labels, threshold)
    EVALUATION_PATH.write_text(json.dumps(evaluation, ensure_ascii=False, indent=2), encoding="utf-8")
    TRAINING_HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    preprocessing_paths = [PREPROCESSING_DIR / name for name in ("categorical_encoder.pkl", "train_only_scaler.pkl", "feature_contract.json", "artifact_manifest.json")]
    metadata = {
        "status": "TRAINED_AND_EVALUATED_PENDING_FINAL_AUDIT",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "feature_order": list(FEATURE_COLUMNS),
        "architecture": MODEL_CONFIG,
        "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
        "seed": {"python": SEED, "numpy": SEED, "torch": SEED},
        "training": {
            "train_rows": int(len(data["train"])),
            "train_anomaly_rows": 0,
            "validation_normal_rows": int(len(validation_normal)),
            "test_rows_not_used_for_training_or_threshold": int(len(data["test"])),
            "best_epoch_by_validation_normal_loss": int(best["epoch"]),
            "best_validation_normal_loss": float(best["validation_loss"]),
            "epochs_run": len(history),
        },
        "threshold": {"path": str(THRESHOLD_PATH), "value": threshold, "method": "P95 train normal"},
        "preprocessing": {
            "contract": "stage2-final-v1",
            "artifact_dir": str(PREPROCESSING_DIR),
            "artifacts_sha256": {path.name: sha256_of(path) for path in preprocessing_paths},
        },
        "artifacts_sha256": {
            "model": sha256_of(MODEL_PATH),
            "config": sha256_of(MODEL_CONFIG_PATH),
            "threshold": sha256_of(THRESHOLD_PATH),
            "evaluation": sha256_of(EVALUATION_PATH),
            "history": sha256_of(TRAINING_HISTORY_PATH),
        },
        "runtime": {"torch": torch.__version__, "python": platform.python_version(), "device": "cpu"},
    }
    MODEL_METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Final VAE training complete")
    print("best_epoch:", best["epoch"], "threshold:", threshold)
    print("test_metrics:", evaluation["splits"]["test"]["metrics"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
