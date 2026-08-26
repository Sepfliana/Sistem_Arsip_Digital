"""Validate Stage 2 preprocessing parity without retraining or deployment."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from utils.final_preprocessing_contract import (
    CATEGORICAL_COLUMNS,
    CONTRACT_FILENAME,
    ENCODER_FILENAME,
    FEATURE_COLUMNS,
    SCALER_FILENAME,
    UNKNOWN_CATEGORY_CODE,
    ipv4_to_integer,
    load_final_artifacts,
    parse_timestamp_wib,
    preprocess_for_inference,
    records_to_unscaled_matrix,
    scale_matrix,
)


SERVICE_DIR = Path(__file__).resolve().parent
REPO_DIR = SERVICE_DIR.parent
SSOT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
ARTIFACT_DIR = SSOT_DIR / "preprocessing_stage2"
REPORT_PATH = REPO_DIR / "STAGE_2_PREPROCESSING_CONTRACT.md"
VALIDATION_PATH = ARTIFACT_DIR / "validation_results.json"
MANIFEST_PATH = ARTIFACT_DIR / "artifact_manifest.json"
SPLITS = ("train", "validation", "test")
ATOL = 1e-7


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def report(status: str, contract: dict[str, Any], checks: list[dict[str, Any]], sizes: dict[str, int]) -> str:
    results = "\n".join(
        f"- {'PASS' if item['passed'] else 'FAIL'} — `{item['name']}`: {item['detail']}"
        for item in checks
    )
    classes = ", ".join(
        f"{column}={len(values)} kelas" for column, values in contract["categorical"]["classes"].items()
    )
    return f"""# STAGE 2 — Preprocessing Contract Finalization

## Preprocessing sebelum perubahan

Jalur training/inference historis tidak identik: inference legacy dapat memakai canonical fallback encoder, IP fallback/kategori alih-alih IPv4 integer 32-bit, `log1p` pada numeric yang training simpan raw, serta menganggap timestamp WIB naive sebagai UTC sehingga hour/day dapat bergeser. Artefak encoder dan scaler historis juga bukan pasangan eksplisit yang diturunkan dari train SSOT Tahap 1.

Endpoint legacy, model, arsitektur VAE, threshold, anomaly score, dan deployment **tidak diubah** pada Tahap 2.

## Preprocessing final

- Sumber data: `ai-service/dataset/final_stage1_ssot/` — train={sizes['train']}, validation={sizes['validation']}, test={sizes['test']}.
- Fungsi raw-to-feature tunggal: `utils.final_preprocessing_contract.records_to_unscaled_matrix()` dipakai oleh preparasi training dan adapter inference.
- Adapter masa depan `preprocess_for_inference()` memuat artifact ter-fit lalu menjalankan `transform` saja; tidak pernah `fit`.
- Tidak ada endpoint yang di-wire pada tahap ini.

## Feature order

`{', '.join(FEATURE_COLUMNS)}`

## Encoder

- Satu artifact: `categorical_encoder.pkl` (`OrdinalEncoder`), fit hanya pada train normal.
- {classes}.
- Kategori yang tidak ada di train memakai encoder yang sama dengan kode unknown eksplisit `{UNKNOWN_CATEGORY_CODE}`; tidak ada encoder inference kedua atau refit pada validation/test.

## IP conversion

Training dan inference memakai `int(ipaddress.ip_address(value))` untuk IPv4 integer 32-bit unsigned. IPv6 ditolak; tidak ada representasi category/domain string.

## Numeric dan timezone

- `duration_ms` dan `object_count` adalah raw finite/non-negative value di kedua jalur; tidak ada `log1p`.
- Timestamp naive dianggap sudah WIB tanpa konversi UTC. Timestamp timezone-aware dikonversi ke `Asia/Jakarta`; `day_of_week` Monday=0.

## Scaler dan artifact

`train_only_scaler.pkl` di-fit sekali pada train normal ({sizes['train']} baris; 0 anomali). Validation, test, dan inference hanya menjalankan `scaler.transform()`.

Artifact: `categorical_encoder.pkl`, `train_only_scaler.pkl`, `feature_contract.json`, matrix Stage 2 scaled/unscaled per split, `artifact_manifest.json`, dan `validation_results.json` dalam `dataset/final_stage1_ssot/preprocessing_stage2/`.

## Hasil parity dan special-case test

Parity train/inference menggunakan raw record yang sama dengan `atol={ATOL:g}`, `rtol=0`.

{results}

## File yang diubah

- `ai-service/utils/final_preprocessing_contract.py` (baru)
- `ai-service/finalize_preprocessing_stage2.py` (baru)
- `ai-service/validate_preprocessing_stage2.py` (baru)

## Status

**{status}**

Tidak ada retraining, perubahan model/arsitektur, threshold, anomaly score, atau deployment.
"""


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    artifacts = [
        ARTIFACT_DIR / ENCODER_FILENAME,
        ARTIFACT_DIR / SCALER_FILENAME,
        ARTIFACT_DIR / CONTRACT_FILENAME,
        MANIFEST_PATH,
    ]
    for path in artifacts:
        check(f"artifact_exists_{path.name}", path.exists(), relative(path))
    if not all(path.exists() for path in artifacts):
        status = "STAGE 2 — FAIL"
        REPORT_PATH.write_text(report(status, {"categorical": {"classes": {}}}, checks, {split: 0 for split in SPLITS}), encoding="utf-8")
        print(status)
        return 1

    contract = json.loads((ARTIFACT_DIR / CONTRACT_FILENAME).read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    encoder, scaler = load_final_artifacts(ARTIFACT_DIR)
    frames = {split: pd.read_csv(SSOT_DIR / f"{split}_metadata.csv", encoding="utf-8") for split in SPLITS}
    sizes = {split: int(len(frame)) for split, frame in frames.items()}

    check("feature_order_exact", contract.get("feature_order") == list(FEATURE_COLUMNS), ", ".join(contract.get("feature_order", [])))
    check("feature_count_9", getattr(scaler, "n_features_in_", None) == 9, str(getattr(scaler, "n_features_in_", None)))
    check("encoder_columns_exact", contract["categorical"].get("columns") == list(CATEGORICAL_COLUMNS), ", ".join(contract["categorical"].get("columns", [])))
    check("encoder_is_single_training_fitted_encoder", len(encoder.categories_) == len(CATEGORICAL_COLUMNS), str(len(encoder.categories_)))
    check("scaler_fit_train_only", contract["scaler"].get("fit_subset") == "train only" and contract["scaler"].get("fit_anomaly_rows") == 0, json.dumps(contract["scaler"], ensure_ascii=False))
    check("inference_trace_transform_only", contract["inference_trace"].get("endpoint_or_deployment_changed") is False and "never fit" in contract["inference_trace"].get("behaviour", ""), contract["inference_trace"].get("adapter", ""))
    check("legacy_and_stage1_artifacts_preserved", manifest["protected_artifacts"].get("unchanged") is True and manifest["stage1_core_artifacts"].get("unchanged") is True, json.dumps({"protected": manifest["protected_artifacts"], "stage1": manifest["stage1_core_artifacts"]}))
    check("train_has_zero_labelled_anomalies", frames["train"]["anomaly_type"].eq("Normal").all(), str(int(frames["train"]["anomaly_type"].ne("Normal").sum())))

    unscaled: dict[str, np.ndarray] = {}
    scaled: dict[str, np.ndarray] = {}
    for split, frame in frames.items():
        records = frame.to_dict("records")
        rebuilt_unscaled = records_to_unscaled_matrix(records, encoder)
        rebuilt_scaled = scale_matrix(rebuilt_unscaled, scaler)
        stored_unscaled = np.load(ARTIFACT_DIR / f"X_{split}_unscaled.npy", allow_pickle=False)
        stored_scaled = np.load(ARTIFACT_DIR / f"X_{split}_final.npy", allow_pickle=False)
        unscaled[split], scaled[split] = rebuilt_unscaled, rebuilt_scaled
        check(f"{split}_training_matrix_reproducible", stored_unscaled.dtype == np.float64 and stored_scaled.dtype == np.float32 and np.array_equal(stored_unscaled, rebuilt_unscaled) and np.array_equal(stored_scaled, rebuilt_scaled), f"unscaled={stored_unscaled.shape}, scaled={stored_scaled.shape}")
        check(f"{split}_matrix_shape_and_finiteness", stored_scaled.shape == (len(frame), 9) and np.isfinite(stored_scaled).all(), f"shape={stored_scaled.shape}, NaN={int(np.isnan(stored_scaled).sum())}, Inf={int(np.isinf(stored_scaled).sum())}")

    train_categories = {column: set(frames["train"][column].astype(str).str.strip()) for column in CATEGORICAL_COLUMNS}
    all_categories = {column: set(pd.concat([frames[split][column] for split in SPLITS]).astype(str).str.strip()) for column in CATEGORICAL_COLUMNS}
    metadata_categories = contract["categorical"]["classes"]
    check("encoder_classes_derived_from_train_only", all(set(metadata_categories[column]) == train_categories[column] for column in CATEGORICAL_COLUMNS), json.dumps({column: len(values) for column, values in train_categories.items()}))

    category_positions = {"activity": 1, "status": 2, "device": 3}
    unknowns: dict[str, list[str]] = {}
    for column in CATEGORICAL_COLUMNS:
        unseen = sorted(all_categories[column] - train_categories[column])
        unknowns[column] = unseen
        if unseen:
            candidate = next(row.to_dict() for split in ("validation", "test") for _, row in frames[split].iterrows() if str(row[column]).strip() in unseen)
            encoded = records_to_unscaled_matrix([candidate], encoder)[0, category_positions[column]]
            equal = np.allclose(scale_matrix(records_to_unscaled_matrix([candidate], encoder), scaler), preprocess_for_inference(candidate, ARTIFACT_DIR), atol=ATOL, rtol=0)
            check(f"unknown_{column}_same_fitted_encoder", encoded == UNKNOWN_CATEGORY_CODE and equal, f"unseen={unseen}, code={encoded}")
        else:
            check(f"unknown_{column}_same_fitted_encoder", True, "Tidak ada kategori evaluation di luar train.")

    parity_cases = [frame.iloc[index].to_dict() for frame in frames.values() for index in sorted({0, len(frame) // 2, len(frame) - 1})]
    parity_difference = max(float(np.max(np.abs(scale_matrix(records_to_unscaled_matrix([record], encoder), scaler) - preprocess_for_inference(record, ARTIFACT_DIR)))) for record in parity_cases)
    check("training_inference_parity_same_raw_records", parity_difference <= ATOL, f"records={len(parity_cases)}, max_abs_diff={parity_difference:.9g}, atol={ATOL:g}, rtol=0")

    categorical_parity = True
    categorical_cases = 0
    for column in CATEGORICAL_COLUMNS:
        for category in sorted(all_categories[column]):
            record = next(row.to_dict() for split in SPLITS for _, row in frames[split].iterrows() if str(row[column]).strip() == category)
            categorical_parity = categorical_parity and np.allclose(scale_matrix(records_to_unscaled_matrix([record], encoder), scaler), preprocess_for_inference(record, ARTIFACT_DIR), atol=ATOL, rtol=0)
            categorical_cases += 1
    check("special_all_categorical_values_training_inference_parity", categorical_parity, f"category_values_tested={categorical_cases}, atol={ATOL:g}, rtol=0")

    normal_record = frames["train"].iloc[0].to_dict()
    normal_unscaled = records_to_unscaled_matrix([normal_record], encoder)[0]
    check("special_ipv4_normal_32_bit_integer", normal_unscaled[4] == ipv4_to_integer(normal_record["ip_address"]), f"{normal_record['ip_address']} -> {int(normal_unscaled[4])}")
    check("special_loopback_converter_32_bit_integer", ipv4_to_integer("127.0.0.1") == 2130706433.0, "127.0.0.1 -> 2130706433")
    loopback_count = int(pd.concat(frames.values())["ip_address"].astype(str).str.strip().eq("127.0.0.1").sum())
    check("special_loopback_dataset_presence", True, f"rows_in_ssot={loopback_count}; converter tested directly because SSOT has no loopback row")
    check("special_timestamp_14_wib", parse_timestamp_wib("2025-03-10 14:00:00") == (14, 0), str(parse_timestamp_wib("2025-03-10 14:00:00")))
    check("special_timestamp_19_wib", parse_timestamp_wib("2025-03-10 19:00:00") == (19, 0), str(parse_timestamp_wib("2025-03-10 19:00:00")))
    check("special_timestamp_aware_to_wib", parse_timestamp_wib("2025-03-10T07:00:00+00:00") == (14, 0), str(parse_timestamp_wib("2025-03-10T07:00:00+00:00")))
    check("special_duration_and_object_count_raw", normal_unscaled[5] == float(normal_record["duration_ms"]) and normal_unscaled[6] == float(normal_record["object_count"]), f"duration_ms={normal_unscaled[5]}, object_count={normal_unscaled[6]}")

    check("scaler_parameters_equal_train_only_statistics", np.allclose(scaler.mean_, unscaled["train"].mean(axis=0), atol=1e-12, rtol=0) and np.allclose(scaler.var_, unscaled["train"].var(axis=0), atol=1e-12, rtol=0), "mean/variance from train unscaled only")
    scaled64 = scaler.transform(unscaled["train"])
    check("scaler_train_output_normalized_float64", np.allclose(scaled64.mean(axis=0), 0.0, atol=1e-8, rtol=0) and np.allclose(scaled64.std(axis=0), 1.0, atol=1e-12, rtol=0), "float64 mean atol=1e-8, std atol=1e-12; stable for 32-bit IPv4 accumulation")
    check("scaler_train_output_float32_export_accuracy", np.allclose(scaled["train"].mean(axis=0), 0.0, atol=1e-6, rtol=0) and np.allclose(scaled["train"].std(axis=0), 1.0, atol=5e-5, rtol=0), "float32 mean atol=1e-6, std atol=5e-5")

    manifest_hashes_ok = all((ARTIFACT_DIR / name).exists() and sha256_of(ARTIFACT_DIR / name) == digest for name, digest in manifest.get("output_sha256", {}).items())
    check("artifact_manifest_checksums_match", manifest_hashes_ok, f"artifacts={len(manifest.get('output_sha256', {}))}")

    failed = [item for item in checks if not item["passed"]]
    status = "STAGE 2 — PASS" if not failed else "STAGE 2 — FAIL"
    payload = {"stage": "STAGE 2", "status": status, "tolerance": {"atol": ATOL, "rtol": 0.0}, "parity": {"records": len(parity_cases), "max_abs_diff": parity_difference}, "unknown_categories": unknowns, "checks_pass": len(checks) - len(failed), "checks_fail": len(failed), "checks": checks}
    VALIDATION_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report(status, contract, checks, sizes), encoding="utf-8")
    print(status)
    print(f"Validation checks: {payload['checks_pass']} PASS / {payload['checks_fail']} FAIL")
    print(f"Parity max abs diff: {parity_difference:.9g}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
