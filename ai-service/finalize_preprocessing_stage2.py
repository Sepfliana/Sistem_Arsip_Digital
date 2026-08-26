"""Build the corrected, single Stage 2 preprocessing artifact set from SSOT."""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from utils.final_preprocessing_contract import (
    CATEGORICAL_COLUMNS,
    CONTRACT_FILENAME,
    ENCODER_FILENAME,
    FEATURE_COLUMNS,
    IP_ZSCORE_BOUNDS,
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
LEGACY_V1_DIR = SSOT_DIR / "preprocessing_stage2_v1_unbounded_legacy"
SPLITS = ("train", "validation", "test")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def load_frames() -> dict[str, pd.DataFrame]:
    expected = {"train": 6692, "validation": 4168, "test": 4140}
    required = {"user_id", "activity", "status", "device", "ip_address", "duration_ms", "object_count", "timestamp", "session_id", "anomaly_type"}
    frames: dict[str, pd.DataFrame] = {}
    for split in SPLITS:
        frame = pd.read_csv(SSOT_DIR / f"{split}_metadata.csv", encoding="utf-8")
        if len(frame) != expected[split] or required - set(frame.columns):
            raise ValueError(f"Metadata SSOT {split} tidak sesuai kontrak/ukuran Stage 1.")
        frames[split] = frame
    if not frames["train"]["anomaly_type"].eq("Normal").all():
        raise ValueError("Train SSOT tidak murni normal; fitting preprocessing dilarang.")
    return frames


def main() -> int:
    stage1 = json.loads((SSOT_DIR / "final_dataset_metadata.json").read_text(encoding="utf-8"))
    if stage1.get("status") != "PASS" or stage1.get("feature_order") != list(FEATURE_COLUMNS):
        raise ValueError("Stage 1 SSOT tidak PASS atau feature order berubah.")
    if not LEGACY_V1_DIR.exists():
        raise FileNotFoundError("Artifact Stage 2 v1 unbounded harus dipreservasi sebelum membangun v2.")
    frames = load_frames()
    records = {name: frame.to_dict("records") for name, frame in frames.items()}
    encoder = fit_categorical_encoder(records["train"])
    unscaled = {name: records_to_unscaled_matrix(rows, encoder) for name, rows in records.items()}
    scaler = StandardScaler().fit(unscaled["train"])
    scaled = {name: scale_matrix(values, scaler) for name, values in unscaled.items()}
    if any(values.shape != (len(frames[name]), 9) or not np.isfinite(values).all() for name, values in scaled.items()):
        raise ValueError("Hasil preprocessing final bukan matrix finite (n, 9).")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for split in SPLITS:
        raw_path, final_path = ARTIFACT_DIR / f"X_{split}_unscaled.npy", ARTIFACT_DIR / f"X_{split}_final.npy"
        np.save(raw_path, unscaled[split]); np.save(final_path, scaled[split])
        paths[raw_path.name], paths[final_path.name] = raw_path, final_path
    encoder_path, scaler_path = ARTIFACT_DIR / ENCODER_FILENAME, ARTIFACT_DIR / SCALER_FILENAME
    with encoder_path.open("wb") as file:
        pickle.dump(encoder, file)
    with scaler_path.open("wb") as file:
        pickle.dump(scaler, file)
    paths[encoder_path.name], paths[scaler_path.name] = encoder_path, scaler_path
    classes = {name: [str(value) for value in values] for name, values in zip(CATEGORICAL_COLUMNS, encoder.categories_, strict=True)}
    contract = {
        "contract_version": "stage2-final-v2-bounded-ip-zscore",
        "source_ssot": relative(SSOT_DIR), "feature_order": list(FEATURE_COLUMNS),
        "categorical": {"columns": list(CATEGORICAL_COLUMNS), "encoder": "sklearn.preprocessing.OrdinalEncoder", "fit_subset": "train normal only", "classes": classes, "unknown_policy": "same fitted encoder emits -1", "unknown_code": UNKNOWN_CATEGORY_CODE},
        "ip_address": {"representation": "raw unsigned IPv4 32-bit integer via int(ipaddress.ip_address(value))", "ipv6_policy": "reject", "scaler": "the same train-only StandardScaler.transform() used by all features", "post_scaler_bounded_zscore": list(IP_ZSCORE_BOUNDS), "reason": "prevent a 246-value private-IP train range from producing unbounded multi-million-sigma input for valid out-of-range IPv4; no labels, anomaly score, or feature weight are used"},
        "numeric": {"duration_ms": "raw finite non-negative; no log1p", "object_count": "raw finite non-negative; no log1p"},
        "temporal": {"timezone": TIMEZONE, "naive_timestamp_policy": "already WIB; no UTC conversion", "aware_timestamp_policy": "convert to Asia/Jakarta", "day_of_week": "Monday=0 through Sunday=6"},
        "scaler": {"type": "sklearn.preprocessing.StandardScaler", "fit_subset": "train only", "fit_rows": len(frames["train"]), "fit_anomaly_rows": 0, "n_features": 9, "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(), "var": scaler.var_.tolist()},
        "inference_trace": {"adapter": "utils.final_preprocessing_contract.preprocess_for_inference", "behaviour": "loads the paired encoder/scaler then transform plus deterministic IP bound only; never fit", "endpoint_or_deployment_changed_by_stage2": False},
        "source_sha256": {f"{name}_metadata.csv": sha256_of(SSOT_DIR / f"{name}_metadata.csv") for name in SPLITS},
        "supersedes": {"version": "stage2-final-v1", "preserved_at": relative(LEGACY_V1_DIR), "reason": "v1 parity passed but unbounded train-only IP z-score caused empirical score domination for valid external IPv4"},
    }
    contract_path = ARTIFACT_DIR / CONTRACT_FILENAME
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    paths[contract_path.name] = contract_path
    manifest = {
        "stage": "STAGE 2", "status": "ARTIFACTS_READY_FOR_VALIDATION", "contract_version": contract["contract_version"],
        "fit_operations": {"categorical_encoder": "train normal only", "standard_scaler": "train normal only", "training_rows": len(frames["train"]), "training_anomaly_rows": 0},
        "outputs": {name: relative(path) for name, path in paths.items()}, "output_sha256": {name: sha256_of(path) for name, path in paths.items()},
        "stage1_core_preserved": True, "v1_unbounded_artifacts_preserved": relative(LEGACY_V1_DIR),
    }
    (ARTIFACT_DIR / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "STAGE 2 ARTIFACTS READY", "contract": contract["contract_version"], "shapes": {key: list(value.shape) for key, value in scaled.items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
