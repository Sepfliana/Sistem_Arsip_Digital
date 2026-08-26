"""Validate corrected Stage 2 training/inference preprocessing parity."""

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
    FEATURE_COLUMNS,
    IP_FEATURE_INDEX,
    IP_ZSCORE_BOUNDS,
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
LEGACY_V1_DIR = SSOT_DIR / "preprocessing_stage2_v1_unbounded_legacy"
REPORT_PATH = REPO_DIR / "STAGE_2_PREPROCESSING_CONTRACT.md"
RESULTS_PATH = ARTIFACT_DIR / "validation_results.json"
SPLITS = ("train", "validation", "test")
ATOL = 1e-7


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report(status: str, checks: list[dict[str, Any]], contract: dict[str, Any]) -> str:
    lines = "\n".join(f"- {'PASS' if item['passed'] else 'FAIL'} — `{item['name']}`: {item['detail']}" for item in checks)
    return f"""# STAGE 2 — Preprocessing Contract Finalization

## Status kontrak

**{status}**

Kontrak v1 sebelumnya membuktikan parity tetapi audit integrasi menemukan z-score IP tidak terbatas: train normal hanya berisi rentang `192.168.1.*` sehingga IPv4 valid di luar rentang itu menghasilkan input multi-juta-sigma dan mendominasi reconstruction error. V1 dipreservasi di `ai-service/dataset/final_stage1_ssot/preprocessing_stage2_v1_unbounded_legacy/`; tidak ada artifact yang dihapus.

## Kontrak final v2

- Sumber: SSOT Tahap 1 (`6.692` train normal, `4.168` validation, `4.140` test), session split tidak diubah.
- Urutan 9 fitur: `{', '.join(FEATURE_COLUMNS)}`.
- `activity`, `status`, dan `device`: satu `OrdinalEncoder`, fit hanya train normal, inference `transform` artifact yang sama.
- IP: IPv4 tetap `int(ipaddress.ip_address(value))` unsigned 32-bit; IPv6 ditolak. Setelah `StandardScaler.transform()` train-only, hanya z-score IP dibatasi deterministik `{IP_ZSCORE_BOUNDS}`. Ini bukan kategorisasi IP, bukan weighting, dan tidak memakai label/threshold; ia mencegah distorsi nilai tak-terbatas sambil mempertahankan satu feature IP.
- `duration_ms` dan `object_count`: raw non-negatif, tanpa `log1p`.
- Timestamp naive adalah WIB; timestamp aware dikonversi ke Asia/Jakarta; `day_of_week` Monday=0.
- Scaler hanya fit train normal. Validation/test/inference hanya transform yang sama, lalu bound IP kontraktual yang sama.

## Artifact final

`categorical_encoder.pkl`, `train_only_scaler.pkl`, `feature_contract.json`, matrix unscaled/final untuk tiga split, `artifact_manifest.json`, dan `validation_results.json` di `ai-service/dataset/final_stage1_ssot/preprocessing_stage2/`.

## Parity dan special case

Toleransi eksplisit: `atol={ATOL:g}`, `rtol=0`.

{lines}

## File kode

- `ai-service/utils/final_preprocessing_contract.py`
- `ai-service/finalize_preprocessing_stage2.py`
- `ai-service/validate_preprocessing_stage2.py`

"""


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    required = [ARTIFACT_DIR / name for name in ("categorical_encoder.pkl", "train_only_scaler.pkl", "feature_contract.json", "artifact_manifest.json")]
    for artifact in required:
        check(f"artifact_exists_{artifact.name}", artifact.exists(), str(artifact))
    if not all(path.exists() for path in required):
        status = "STAGE 2 — FAIL"
        REPORT_PATH.write_text(report(status, checks, {}), encoding="utf-8")
        return 1
    contract = json.loads((ARTIFACT_DIR / "feature_contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((ARTIFACT_DIR / "artifact_manifest.json").read_text(encoding="utf-8"))
    encoder, scaler = load_final_artifacts(ARTIFACT_DIR)
    frames = {name: pd.read_csv(SSOT_DIR / f"{name}_metadata.csv", encoding="utf-8") for name in SPLITS}
    check("contract_version_final_bounded_ip", contract.get("contract_version") == "stage2-final-v2-bounded-ip-zscore", contract.get("contract_version", ""))
    check("feature_order_exact_9", contract.get("feature_order") == list(FEATURE_COLUMNS), ", ".join(contract.get("feature_order", [])))
    check("non_input_fields_not_in_matrix", not {"session_id", "username", "role", "risk_level", "anomaly_type"}.intersection(FEATURE_COLUMNS), "metadata/labels excluded")
    check("encoder_train_only_three_categoricals", contract["categorical"].get("columns") == list(CATEGORICAL_COLUMNS) and len(encoder.categories_) == 3, str(contract["categorical"].get("columns")))
    check("scaler_train_normal_only", contract["scaler"].get("fit_subset") == "train only" and contract["scaler"].get("fit_anomaly_rows") == 0 and frames["train"]["anomaly_type"].eq("Normal").all(), "6692 train / 0 anomaly")
    check("v1_unbounded_artifact_preserved", LEGACY_V1_DIR.exists() and manifest.get("v1_unbounded_artifacts_preserved", "").endswith("preprocessing_stage2_v1_unbounded_legacy"), str(LEGACY_V1_DIR))

    rebuilt: dict[str, np.ndarray] = {}
    for split, frame in frames.items():
        raw = records_to_unscaled_matrix(frame.to_dict("records"), encoder)
        final = scale_matrix(raw, scaler)
        stored_raw = np.load(ARTIFACT_DIR / f"X_{split}_unscaled.npy", allow_pickle=False)
        stored_final = np.load(ARTIFACT_DIR / f"X_{split}_final.npy", allow_pickle=False)
        rebuilt[split] = raw
        check(f"{split}_reproducible", np.array_equal(raw, stored_raw) and np.array_equal(final, stored_final), f"shape={final.shape}")
        check(f"{split}_finite_shape", final.shape == (len(frame), 9) and np.isfinite(final).all(), f"shape={final.shape}")
        check(f"{split}_ip_zscore_bounded", bool((final[:, IP_FEATURE_INDEX] >= IP_ZSCORE_BOUNDS[0]).all() and (final[:, IP_FEATURE_INDEX] <= IP_ZSCORE_BOUNDS[1]).all()), f"min={final[:, IP_FEATURE_INDEX].min():.6f}, max={final[:, IP_FEATURE_INDEX].max():.6f}")
    check("scaler_parameters_from_train_raw_only", np.allclose(scaler.mean_, rebuilt["train"].mean(axis=0), atol=1e-12, rtol=0) and np.allclose(scaler.var_, rebuilt["train"].var(axis=0), atol=1e-12, rtol=0), "mean/variance exact from train raw matrix")

    samples = [frame.iloc[index].to_dict() for frame in frames.values() for index in sorted({0, len(frame) // 2, len(frame) - 1})]
    differences = []
    for record in samples:
        train_path = scale_matrix(records_to_unscaled_matrix([record], encoder), scaler)
        inference_path = preprocess_for_inference(record, ARTIFACT_DIR)
        differences.append(float(np.max(np.abs(train_path - inference_path))))
    maximum_difference = max(differences)
    check("training_inference_parity_same_raw", maximum_difference <= ATOL, f"max_abs_diff={maximum_difference:.9g}; atol={ATOL:g}; rtol=0")

    category_parity = True
    for column in CATEGORICAL_COLUMNS:
        for value in sorted(pd.concat([frames[name][column] for name in SPLITS]).astype(str).unique()):
            record = next(row.to_dict() for frame in frames.values() for _, row in frame.iterrows() if str(row[column]) == value)
            category_parity &= np.allclose(scale_matrix(records_to_unscaled_matrix([record], encoder), scaler), preprocess_for_inference(record, ARTIFACT_DIR), atol=ATOL, rtol=0)
    check("special_all_categorical_values_parity", bool(category_parity), "activity/status/device train and unseen evaluation values")

    base = frames["train"].iloc[0].to_dict()
    ip_cases = {"normal_private": base["ip_address"], "loopback": "127.0.0.1", "other_private": "10.0.0.1", "public": "8.8.8.8"}
    ip_pass = True
    ip_details: list[str] = []
    for label, ip in ip_cases.items():
        record = dict(base); record["ip_address"] = ip
        raw = records_to_unscaled_matrix([record], encoder)
        transformed = preprocess_for_inference(record, ARTIFACT_DIR)
        expected = scale_matrix(raw, scaler)
        ip_pass &= raw[0, IP_FEATURE_INDEX] == ipv4_to_integer(ip) and np.array_equal(transformed, expected) and IP_ZSCORE_BOUNDS[0] <= transformed[0, IP_FEATURE_INDEX] <= IP_ZSCORE_BOUNDS[1]
        ip_details.append(f"{label}={ip}->{int(raw[0, IP_FEATURE_INDEX])},z={transformed[0, IP_FEATURE_INDEX]:.3f}")
    check("special_ipv4_integer_and_bounded_parity", bool(ip_pass), "; ".join(ip_details))
    check("special_timestamp_14_wib", parse_timestamp_wib("2025-03-10 14:00:00") == (14, 0), str(parse_timestamp_wib("2025-03-10 14:00:00")))
    check("special_timestamp_19_wib", parse_timestamp_wib("2025-03-10 19:00:00") == (19, 0), str(parse_timestamp_wib("2025-03-10 19:00:00")))
    check("special_timestamp_midnight_day", parse_timestamp_wib("2025-03-09 23:59:59") == (23, 6) and parse_timestamp_wib("2025-03-10 00:00:00") == (0, 0), "Sunday 23:59 -> Monday 00:00")
    check("special_numeric_raw", records_to_unscaled_matrix([base], encoder)[0, 5] == float(base["duration_ms"]) and records_to_unscaled_matrix([base], encoder)[0, 6] == float(base["object_count"]), "duration_ms/object_count unchanged before scaling")
    check("manifest_output_checksums", all(sha256_of(ARTIFACT_DIR / name) == digest for name, digest in manifest.get("output_sha256", {}).items()), f"count={len(manifest.get('output_sha256', {}))}")

    failures = [item for item in checks if not item["passed"]]
    status = "STAGE 2 — PASS" if not failures else "STAGE 2 — FAIL"
    payload = {"stage": "STAGE 2", "status": status, "contract_version": contract.get("contract_version"), "tolerance": {"atol": ATOL, "rtol": 0}, "parity": {"max_abs_diff": maximum_difference, "records": len(samples)}, "checks_pass": len(checks) - len(failures), "checks_fail": len(failures), "checks": checks}
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report(status, checks, contract), encoding="utf-8")
    print(status)
    print(json.dumps({"checks_pass": payload["checks_pass"], "checks_fail": payload["checks_fail"], "max_abs_diff": maximum_difference}, ensure_ascii=False))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
