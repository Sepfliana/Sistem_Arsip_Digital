"""Build Stage 2 preprocessing artifacts from the Stage 1 dataset SSOT.

This script performs preprocessing artifact fitting only.  It does not import a
VAE, train a model, calculate a threshold, produce an anomaly score, or wire an
endpoint.  The separate validator proves training/inference parity afterwards.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from utils.final_preprocessing_contract import (
    CATEGORICAL_COLUMNS,
    CONTRACT_FILENAME,
    ENCODER_FILENAME,
    FEATURE_COLUMNS,
    SCALER_FILENAME,
    TIMEZONE,
    UNKNOWN_CATEGORY_CODE,
    fit_categorical_encoder,
    records_to_unscaled_matrix,
    scale_matrix,
)


SERVICE_DIR = Path(__file__).resolve().parent
REPO_DIR = SERVICE_DIR.parent
SSOT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
ARTIFACT_DIR = SSOT_DIR / "preprocessing_stage2"

SPLITS = ("train", "validation", "test")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def hash_tree(paths: Iterable[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            hashes[relative(path)] = sha256_of(path)
        elif path.exists():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                hashes[relative(child)] = sha256_of(child)
    return hashes


def stage1_core_hashes() -> dict[str, str]:
    """Hash Stage 1 files while excluding this Stage 2 child artifact directory."""
    hashes: dict[str, str] = {}
    for child in sorted(SSOT_DIR.iterdir()):
        if child == ARTIFACT_DIR:
            continue
        if child.is_file():
            hashes[relative(child)] = sha256_of(child)
    return hashes


def load_split_metadata() -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    required_columns = {
        "row_id",
        "session_id",
        "user_id",
        "activity",
        "status",
        "device",
        "ip_address",
        "duration_ms",
        "object_count",
        "timestamp",
        "risk_level",
        "anomaly_type",
    }
    for split in SPLITS:
        path = SSOT_DIR / f"{split}_metadata.csv"
        if not path.exists():
            raise FileNotFoundError(f"Metadata SSOT Tahap 1 tidak ditemukan: {path}")
        frame = pd.read_csv(path, encoding="utf-8")
        missing = sorted(required_columns - set(frame.columns))
        if missing:
            raise ValueError(f"Metadata {split} kehilangan kolom: {missing}")
        frames[split] = frame
    return frames


def main() -> int:
    stage1_metadata_path = SSOT_DIR / "final_dataset_metadata.json"
    if not stage1_metadata_path.exists():
        raise FileNotFoundError("SSOT Tahap 1 tidak ditemukan; Tahap 2 tidak dapat dimulai.")
    stage1_metadata = json.loads(stage1_metadata_path.read_text(encoding="utf-8"))
    if stage1_metadata.get("status") != "PASS" or stage1_metadata.get("feature_order") != list(FEATURE_COLUMNS):
        raise ValueError("SSOT Tahap 1 bukan dataset PASS dengan kontrak sembilan fitur yang diperlukan.")

    protected_before = hash_tree(
        [
            SERVICE_DIR / "models",
            SERVICE_DIR / "model",
            SERVICE_DIR / "dataset" / "preprocessed",
            SERVICE_DIR / "dataset" / "final",
            SERVICE_DIR / "dataset" / "encoded",
            SERVICE_DIR / "dataset" / "feature_engineering",
            SERVICE_DIR / "dataset" / "generator" / "raw",
            SERVICE_DIR / "app.py",
            SERVICE_DIR / "services" / "inference.py",
            SERVICE_DIR / "services" / "inference_stage11.py",
            SERVICE_DIR / "utils" / "preprocessing.py",
            SERVICE_DIR / "utils" / "preprocessing_contract.py",
        ]
    )
    stage1_before = stage1_core_hashes()

    frames = load_split_metadata()
    if not frames["train"]["anomaly_type"].eq("Normal").all():
        raise ValueError("SSOT Tahap 1 train tidak murni Normal; encoder/scaler tidak boleh di-fit.")

    records = {split: frames[split].to_dict("records") for split in SPLITS}

    # The only fitting operations in Stage 2.  Both receive train records only.
    categorical_encoder = fit_categorical_encoder(records["train"])
    unscaled = {
        split: records_to_unscaled_matrix(split_records, categorical_encoder)
        for split, split_records in records.items()
    }
    scaler = StandardScaler().fit(unscaled["train"])
    scaled = {split: scale_matrix(values, scaler) for split, values in unscaled.items()}

    if categorical_encoder.categories_ is None or len(categorical_encoder.categories_) != len(CATEGORICAL_COLUMNS):
        raise ValueError("Categorical encoder tidak memiliki tiga feature kategorikal.")
    if getattr(scaler, "n_features_in_", None) != len(FEATURE_COLUMNS):
        raise ValueError("Scaler Stage 2 harus di-fit pada sembilan fitur.")
    if any(matrix.shape[1] != len(FEATURE_COLUMNS) or not np.isfinite(matrix).all() for matrix in scaled.values()):
        raise ValueError("Hasil preprocessing Stage 2 tidak valid.")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, Path] = {}
    for split in SPLITS:
        unscaled_path = ARTIFACT_DIR / f"X_{split}_unscaled.npy"
        scaled_path = ARTIFACT_DIR / f"X_{split}_final.npy"
        np.save(unscaled_path, unscaled[split])
        np.save(scaled_path, scaled[split])
        artifact_paths[unscaled_path.name] = unscaled_path
        artifact_paths[scaled_path.name] = scaled_path

    encoder_path = ARTIFACT_DIR / ENCODER_FILENAME
    with encoder_path.open("wb") as handle:
        pickle.dump(categorical_encoder, handle)
    artifact_paths[encoder_path.name] = encoder_path

    scaler_path = ARTIFACT_DIR / SCALER_FILENAME
    with scaler_path.open("wb") as handle:
        pickle.dump(scaler, handle)
    artifact_paths[scaler_path.name] = scaler_path

    category_classes = {
        column: [str(value) for value in categories]
        for column, categories in zip(CATEGORICAL_COLUMNS, categorical_encoder.categories_, strict=True)
    }
    source_hashes = {
        f"{split}_metadata.csv": sha256_of(SSOT_DIR / f"{split}_metadata.csv")
        for split in SPLITS
    }
    source_hashes["stage1_final_dataset_metadata.json"] = sha256_of(stage1_metadata_path)
    contract = {
        "contract_version": "stage2-final-v1",
        "source_ssot": relative(SSOT_DIR),
        "feature_order": list(FEATURE_COLUMNS),
        "categorical": {
            "columns": list(CATEGORICAL_COLUMNS),
            "encoder": "sklearn.preprocessing.OrdinalEncoder",
            "fit_subset": "train metadata from Stage 1 SSOT only",
            "classes": category_classes,
            "unknown_policy": "same fitted encoder emits -1 for values absent from training",
            "unknown_code": UNKNOWN_CATEGORY_CODE,
        },
        "ip_address": {
            "representation": "unsigned IPv4 32-bit integer via int(ipaddress.ip_address(value))",
            "ipv6_policy": "reject",
        },
        "numeric": {
            "duration_ms": "raw finite non-negative value; no log1p",
            "object_count": "raw finite non-negative value; no log1p",
        },
        "temporal": {
            "timezone": TIMEZONE,
            "naive_timestamp_policy": "already WIB; no UTC conversion",
            "aware_timestamp_policy": "convert to Asia/Jakarta",
            "day_of_week": "Monday=0 through Sunday=6",
        },
        "scaler": {
            "type": "sklearn.preprocessing.StandardScaler",
            "fit_subset": "train only",
            "fit_rows": int(len(frames["train"])),
            "fit_anomaly_rows": 0,
            "n_features": len(FEATURE_COLUMNS),
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "var": scaler.var_.tolist(),
        },
        "inference_trace": {
            "adapter": "utils.final_preprocessing_contract.preprocess_for_inference",
            "behaviour": "loads Stage 2 encoder and scaler; transform only; never fit",
            "endpoint_or_deployment_changed": False,
        },
        "source_sha256": source_hashes,
    }
    contract_path = ARTIFACT_DIR / CONTRACT_FILENAME
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_paths[contract_path.name] = contract_path

    protected_after = hash_tree(
        [
            SERVICE_DIR / "models",
            SERVICE_DIR / "model",
            SERVICE_DIR / "dataset" / "preprocessed",
            SERVICE_DIR / "dataset" / "final",
            SERVICE_DIR / "dataset" / "encoded",
            SERVICE_DIR / "dataset" / "feature_engineering",
            SERVICE_DIR / "dataset" / "generator" / "raw",
            SERVICE_DIR / "app.py",
            SERVICE_DIR / "services" / "inference.py",
            SERVICE_DIR / "services" / "inference_stage11.py",
            SERVICE_DIR / "utils" / "preprocessing.py",
            SERVICE_DIR / "utils" / "preprocessing_contract.py",
        ]
    )
    stage1_after = stage1_core_hashes()
    if protected_before != protected_after or stage1_before != stage1_after:
        raise RuntimeError("Artefak legacy/production atau inti SSOT Tahap 1 berubah; Stage 2 dihentikan.")

    manifest = {
        "stage": "STAGE 2",
        "status": "ARTIFACTS_READY_FOR_VALIDATION",
        "fit_operations": {
            "categorical_encoder": "train only",
            "standard_scaler": "train only",
            "training_rows": int(len(frames["train"])),
            "training_anomaly_rows": 0,
        },
        "source_sha256": source_hashes,
        "outputs": {name: relative(path) for name, path in artifact_paths.items()},
        "output_sha256": {name: sha256_of(path) for name, path in artifact_paths.items()},
        "protected_artifacts": {"count": len(protected_before), "unchanged": True},
        "stage1_core_artifacts": {"count": len(stage1_before), "unchanged": True},
    }
    manifest_path = ARTIFACT_DIR / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("STAGE 2 preprocessing artifacts ready")
    print(f"Artifact directory: {relative(ARTIFACT_DIR)}")
    print("Train rows / anomaly rows:", len(frames["train"]), "/", 0)
    print("Feature shapes:", {split: matrix.shape for split, matrix in scaled.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
