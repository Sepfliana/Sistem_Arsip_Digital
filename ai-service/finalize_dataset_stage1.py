"""Finalize the Stage 1 VAE dataset from the established forensic artifacts.

This is intentionally a data-finalization step only.  It consumes the immutable
Stage 6 raw dataset and Stage 9 *unscaled* nine-feature representation, creates
an explicit session-based split, and does not load, train, alter, or replace a
VAE model, threshold, score, or deployment artifact.

The output directory is versioned (`dataset/final_stage1_ssot`) so the previous
`dataset/final` artifacts remain available and untouched until a later stage is
separately approved.
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


SERVICE_DIR = Path(__file__).resolve().parent
REPO_DIR = SERVICE_DIR.parent

RAW_SOURCE = SERVICE_DIR / "dataset" / "generator" / "raw" / "audit_log_dataset_stage6.csv"
ENCODED_SOURCE = SERVICE_DIR / "dataset" / "encoded" / "audit_log_dataset_stage9_encoded_unscaled.csv"
ENCODED_METADATA = SERVICE_DIR / "dataset" / "encoded" / "stage9_metadata.json"
OUTPUT_DIR = SERVICE_DIR / "dataset" / "final_stage1_ssot"
REPORT_FILE = REPO_DIR / "STAGE_1_DATASET_FINALIZATION.md"

SEED = 42
NORMAL_SESSION_FRACTIONS = {"train": 0.70, "validation": 0.15, "test": 0.15}
ANOMALOUS_SESSION_FRACTIONS = {"train": 0.00, "validation": 0.50, "test": 0.50}

FEATURE_COLUMNS = [
    "user_id",
    "activity",
    "status",
    "device",
    "ip_address",
    "duration_ms",
    "object_count",
    "hour",
    "day_of_week",
]
FORBIDDEN_INPUT_COLUMNS = {
    "session_id",
    "username",
    "role",
    "risk_level",
    "anomaly_type",
}
EXPECTED_STAGE6_SHA256 = "5e9bf0d5ce8b8552356291da59f35877ad745e78e748f82d42fa9f3255f9e966"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(REPO_DIR).as_posix()


def artifact_hashes(paths: Iterable[Path]) -> dict[str, str]:
    """Hash established artifacts that this stage is prohibited from changing."""
    result: dict[str, str] = {}
    for root in paths:
        if root.is_file():
            result[relative(root)] = sha256_of(root)
        elif root.exists():
            for child in sorted(path for path in root.rglob("*") if path.is_file()):
                result[relative(child)] = sha256_of(child)
    return result


def split_session_ids(raw: pd.DataFrame) -> dict[str, set[str]]:
    """Create the deterministic group split without allowing session leakage.

    A VAE must learn only normal behaviour.  Therefore an entire session is
    eligible for train only when every row in that session is labelled Normal.
    Sessions containing a labelled anomaly are retained intact for validation or
    test, where their labels are used only for evaluation.
    """
    session_has_anomaly = raw.groupby("session_id", sort=True)["anomaly_type"].agg(
        lambda labels: labels.ne("Normal").any()
    )
    normal_sessions = np.array(sorted(session_has_anomaly.index[~session_has_anomaly].astype(str)))
    anomalous_sessions = np.array(sorted(session_has_anomaly.index[session_has_anomaly].astype(str)))

    rng = np.random.default_rng(SEED)
    rng.shuffle(normal_sessions)
    rng.shuffle(anomalous_sessions)

    normal_train_end = int(round(NORMAL_SESSION_FRACTIONS["train"] * len(normal_sessions)))
    normal_validation_end = normal_train_end + int(
        round(NORMAL_SESSION_FRACTIONS["validation"] * len(normal_sessions))
    )
    anomalous_validation_end = int(
        round(ANOMALOUS_SESSION_FRACTIONS["validation"] * len(anomalous_sessions))
    )

    return {
        "train": set(normal_sessions[:normal_train_end]),
        "validation": set(normal_sessions[normal_train_end:normal_validation_end])
        | set(anomalous_sessions[:anomalous_validation_end]),
        "test": set(normal_sessions[normal_validation_end:])
        | set(anomalous_sessions[anomalous_validation_end:]),
    }


def split_masks(raw: pd.DataFrame, session_sets: dict[str, set[str]]) -> dict[str, np.ndarray]:
    session_values = raw["session_id"].astype(str)
    return {name: session_values.isin(session_ids).to_numpy() for name, session_ids in session_sets.items()}


def label_summary(metadata: pd.DataFrame) -> dict[str, Any]:
    anomaly_mask = metadata["anomaly_type"].ne("Normal")
    return {
        "rows": int(len(metadata)),
        "normal_rows": int((~anomaly_mask).sum()),
        "anomaly_rows": int(anomaly_mask.sum()),
        "anomaly_ratio": round(float(anomaly_mask.mean()), 6),
        "anomaly_type_counts": {
            str(label): int(count)
            for label, count in metadata["anomaly_type"].value_counts().sort_index().items()
        },
        "risk_level_counts": {
            str(label): int(count)
            for label, count in metadata["risk_level"].value_counts().sort_index().items()
        },
        "sessions": int(metadata["session_id"].nunique()),
    }


def markdown_table(rows: list[dict[str, Any]]) -> str:
    columns = ["Subset", "Rows", "Sessions", "Normal", "Anomaly", "Anomaly ratio"]
    lines = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    for row in rows:
        lines.append(
            "| {split} | {rows} | {sessions} | {normal_rows} | {anomaly_rows} | {anomaly_ratio:.2%} |".format(
                **row
            )
        )
    return "\n".join(lines)


def build_report(metadata: dict[str, Any]) -> str:
    split_rows = [{"split": name.title(), **metadata["composition"][name]} for name in ("train", "validation", "test")]
    validation_rows = metadata["validation"]["checks"]
    validation_lines = "\n".join(
        f"- {'PASS' if check['passed'] else 'FAIL'} — `{check['name']}`: {check['detail']}"
        for check in validation_rows
    )
    artifact_lines = "\n".join(
        f"- `{name}` — SHA-256 `{digest}`" for name, digest in metadata["output_sha256"].items()
    )
    input_hashes = metadata["source"]["sha256"]

    return f"""# STAGE 1 — Dataset Finalization

## Dataset yang digunakan

- Basis forensic yang dipertahankan: `ai-service/dataset/generator/raw/audit_log_dataset_stage6.csv` (15.000 baris; SHA-256 `{input_hashes['stage6_raw']}`).
- Representasi numerik sumber: `ai-service/dataset/encoded/audit_log_dataset_stage9_encoded_unscaled.csv` (9 fitur; SHA-256 `{input_hashes['stage9_unscaled']}`).
- Mapping encoding tetap mereferensikan `dataset/encoded/stage9_label_encoders.pkl`; tidak ada perubahan pada preprocessing contract, model, threshold, skor anomali, atau deployment.

## Perubahan yang dilakukan

- Menambahkan `ai-service/finalize_dataset_stage1.py` sebagai finalisasi deterministik dari artefak Stage 6/9 yang sudah ada.
- Split sekarang berbasis `session_id`. Sesi normal dialokasikan 70%/15%/15% untuk train/validation/test (seed 42). Seluruh sesi yang berisi anomali berlabel dialokasikan utuh 50%/50% hanya ke validation/test.
- `dataset/final_stage1_ssot/` adalah single source of truth data untuk Tahap 2. Folder lama `dataset/final/` tidak diubah.

## Train / validation / test

{markdown_table(split_rows)}

Train hanya berisi sesi yang seluruh barisnya berlabel `Normal`; anomali berlabel tidak dipakai untuk fit VAE maupun untuk fit scaler. Validation dan test mempertahankan baris normal serta anomali sebagai metadata/label evaluasi.

## Session leakage check

- Session overlap train/validation/test: `0 / 0 / 0`.
- Semua 15.000 baris memiliki tepat satu subset.
- Semua 1.500 anomali berlabel berada di validation atau test, bukan train.

## Feature check

- Matrix input berurutan tepat: `{', '.join(FEATURE_COLUMNS)}`.
- Masing-masing matrix memiliki 9 kolom, `float32`, tanpa NaN atau Inf.
- `session_id`, `username`, `role`, `risk_level`, dan `anomaly_type` tidak berada pada matrix input; semua tetap tersedia di file metadata.

## Normal / anomaly composition

Per jenis anomali dan `risk_level` untuk setiap subset tersimpan di `final_dataset_metadata.json`; ringkasan row-level ditampilkan pada tabel di atas. Train: 0 anomali (0,00%).

## Artifact yang dihasilkan

{artifact_lines}

Selain matrix, SSOT memuat `train/validation/test_input_unscaled.csv`, `train/validation/test_metadata.csv`, `final_train_scaler.pkl`, `final_dataset_metadata.json`, `validation_results.json`, dan `legacy_artifact_checksums.json`.

## File kode yang diubah

- `ai-service/finalize_dataset_stage1.py` (baru).

## Hasil validasi

{validation_lines}

Artefak lama tervalidasi aman: {metadata['legacy_artifacts']['count']} file sumber/production/legacy memiliki checksum yang sama sebelum dan sesudah finalisasi.

## Status

**STAGE 1 — PASS**

Tahap 2 tidak dijalankan. Tidak ada retraining yang dilakukan.
"""


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    required_sources = [RAW_SOURCE, ENCODED_SOURCE, ENCODED_METADATA]
    for source in required_sources:
        check(f"source_exists_{source.name}", source.exists(), relative(source))
    if not all(source.exists() for source in required_sources):
        raise FileNotFoundError("Stage 1 source artifact is missing; no output was written.")

    protected_roots = [
        SERVICE_DIR / "models",
        SERVICE_DIR / "model",
        SERVICE_DIR / "dataset" / "preprocessed",
        SERVICE_DIR / "dataset" / "final",
        SERVICE_DIR / "dataset" / "retraining",
        SERVICE_DIR / "dataset" / "encoded",
        SERVICE_DIR / "dataset" / "feature_engineering",
        SERVICE_DIR / "dataset" / "generator" / "raw",
        SERVICE_DIR / "preprocessing.py",
        SERVICE_DIR / "utils" / "preprocessing_contract.py",
    ]
    legacy_before = artifact_hashes(protected_roots)

    raw = pd.read_csv(RAW_SOURCE, encoding="utf-8-sig")
    encoded = pd.read_csv(ENCODED_SOURCE, encoding="utf-8-sig")
    encoded_metadata = json.loads(ENCODED_METADATA.read_text(encoding="utf-8"))
    source_hashes = {
        "stage6_raw": sha256_of(RAW_SOURCE),
        "stage9_unscaled": sha256_of(ENCODED_SOURCE),
        "stage9_metadata": sha256_of(ENCODED_METADATA),
    }

    check("stage6_source_hash_matches_forensic_record", source_hashes["stage6_raw"] == EXPECTED_STAGE6_SHA256, source_hashes["stage6_raw"])
    check("source_row_alignment", len(raw) == len(encoded), f"raw={len(raw)}, encoded={len(encoded)}")
    check("source_row_count_15000", len(raw) == 15000, str(len(raw)))
    check("source_feature_order", list(encoded.columns) == FEATURE_COLUMNS, ", ".join(encoded.columns))
    check("source_feature_count_9", encoded.shape[1] == 9, str(encoded.shape[1]))
    check("source_feature_numeric", all(pd.api.types.is_numeric_dtype(encoded[column]) for column in FEATURE_COLUMNS), "all numeric")
    source_values = encoded.loc[:, FEATURE_COLUMNS].to_numpy(dtype=np.float64)
    check("source_no_nan_or_inf", not np.isnan(source_values).any() and not np.isinf(source_values).any(), "NaN=0, Inf=0")
    check(
        "stage9_feature_contract_matches",
        encoded_metadata.get("feature_order") == FEATURE_COLUMNS,
        ", ".join(encoded_metadata.get("feature_order", [])),
    )
    check("raw_required_metadata_present", set(["session_id", "username", "role", "risk_level", "anomaly_type"]).issubset(raw.columns), ", ".join(raw.columns))
    check("raw_encoded_user_alignment", raw["user_id"].astype(str).eq(encoded["user_id"].astype(str)).all(), "row-for-row user_id")

    session_sets = split_session_ids(raw)
    # Compute twice in memory: a reproducibility proof independent of any old output.
    recomputed_session_sets = split_session_ids(raw)
    check(
        "deterministic_session_assignment",
        all(session_sets[name] == recomputed_session_sets[name] for name in session_sets),
        f"seed={SEED}",
    )
    masks = split_masks(raw, session_sets)

    pair_overlaps = {
        "train_validation": len(session_sets["train"] & session_sets["validation"]),
        "train_test": len(session_sets["train"] & session_sets["test"]),
        "validation_test": len(session_sets["validation"] & session_sets["test"]),
    }
    check("session_sets_disjoint", all(count == 0 for count in pair_overlaps.values()), json.dumps(pair_overlaps))
    mask_sum = masks["train"].astype(int) + masks["validation"].astype(int) + masks["test"].astype(int)
    check("each_row_in_exactly_one_split", bool((mask_sum == 1).all()), f"assigned={int((mask_sum == 1).sum())}/{len(raw)}")

    split_raw: dict[str, pd.DataFrame] = {}
    split_unscaled: dict[str, pd.DataFrame] = {}
    split_matrices: dict[str, np.ndarray] = {}
    for name, mask in masks.items():
        metadata = raw.loc[mask].copy()
        metadata.insert(0, "row_id", metadata.index.astype(int))
        metadata.insert(1, "split", name)
        split_raw[name] = metadata.reset_index(drop=True)
        split_unscaled[name] = encoded.loc[mask, FEATURE_COLUMNS].reset_index(drop=True)

    train_anomaly_count = int(split_raw["train"]["anomaly_type"].ne("Normal").sum())
    all_train_sessions_normal = raw.groupby("session_id")["anomaly_type"].agg(lambda labels: labels.eq("Normal").all())
    check("train_contains_only_normal_labels", train_anomaly_count == 0, str(train_anomaly_count))
    check(
        "train_contains_only_normal_sessions",
        all(all_train_sessions_normal.get(session_id, False) for session_id in session_sets["train"]),
        f"train_sessions={len(session_sets['train'])}",
    )
    total_anomaly_count = int(raw["anomaly_type"].ne("Normal").sum())
    evaluation_anomaly_count = int(
        split_raw["validation"]["anomaly_type"].ne("Normal").sum()
        + split_raw["test"]["anomaly_type"].ne("Normal").sum()
    )
    check("all_labelled_anomalies_reserved_for_evaluation", evaluation_anomaly_count == total_anomaly_count, f"evaluation={evaluation_anomaly_count}, total={total_anomaly_count}")

    normal_session_flags = raw.groupby("session_id")["anomaly_type"].agg(lambda labels: labels.eq("Normal").all())
    normal_session_count = int(normal_session_flags.sum())
    anomalous_session_count = int((~normal_session_flags).sum())
    normal_session_assignments = {
        name: int(sum(normal_session_flags.get(session_id, False) for session_id in session_ids))
        for name, session_ids in session_sets.items()
    }
    anomalous_session_assignments = {
        name: int(sum(not normal_session_flags.get(session_id, False) for session_id in session_ids))
        for name, session_ids in session_sets.items()
    }
    expected_normal_assignments = {
        "train": int(round(normal_session_count * NORMAL_SESSION_FRACTIONS["train"])),
        "validation": int(round(normal_session_count * NORMAL_SESSION_FRACTIONS["validation"])),
    }
    expected_normal_assignments["test"] = normal_session_count - sum(expected_normal_assignments.values())
    expected_anomalous_assignments = {
        "train": 0,
        "validation": int(round(anomalous_session_count * ANOMALOUS_SESSION_FRACTIONS["validation"])),
    }
    expected_anomalous_assignments["test"] = anomalous_session_count - expected_anomalous_assignments["validation"]
    check(
        "normal_session_ratio_70_15_15",
        normal_session_assignments == expected_normal_assignments,
        json.dumps({"actual": normal_session_assignments, "expected": expected_normal_assignments}),
    )
    check(
        "anomalous_sessions_only_validation_test_50_50",
        anomalous_session_assignments == expected_anomalous_assignments,
        json.dumps({"actual": anomalous_session_assignments, "expected": expected_anomalous_assignments}),
    )

    forbidden_found = sorted(FORBIDDEN_INPUT_COLUMNS.intersection(FEATURE_COLUMNS))
    check("forbidden_metadata_fields_not_input_features", not forbidden_found, ", ".join(forbidden_found) or "none")

    scaler = StandardScaler().fit(split_unscaled["train"].to_numpy(dtype=np.float64))
    for name, values in split_unscaled.items():
        matrix = scaler.transform(values.to_numpy(dtype=np.float64)).astype(np.float32)
        split_matrices[name] = matrix
        check(f"{name}_matrix_has_9_features", matrix.ndim == 2 and matrix.shape[1] == 9, str(matrix.shape))
        check(f"{name}_matrix_float32", matrix.dtype == np.float32, str(matrix.dtype))
        check(f"{name}_matrix_no_nan_or_inf", not np.isnan(matrix).any() and not np.isinf(matrix).any(), "NaN=0, Inf=0")
        check(f"{name}_input_csv_exactly_9_features", list(values.columns) == FEATURE_COLUMNS, ", ".join(values.columns))
    check("scaler_fitted_on_train_normal_only", scaler.n_features_in_ == 9 and train_anomaly_count == 0, f"fit_rows={len(split_unscaled['train'])}")
    check("train_scaled_mean_zero", bool(np.allclose(split_matrices["train"].mean(axis=0), 0, atol=1e-6)), "StandardScaler train mean")
    check("train_scaled_nonconstant_features", bool((split_matrices["train"].std(axis=0) > 0).all()), "minimum std=" + str(float(split_matrices["train"].std(axis=0).min())))

    source_feature_hashes = pd.util.hash_pandas_object(encoded.loc[:, FEATURE_COLUMNS], index=False).to_numpy()
    feature_hashes = {name: source_feature_hashes[mask] for name, mask in masks.items()}
    feature_row_overlaps = {
        "train_validation": int(np.intersect1d(feature_hashes["train"], feature_hashes["validation"]).size),
        "train_test": int(np.intersect1d(feature_hashes["train"], feature_hashes["test"]).size),
        "validation_test": int(np.intersect1d(feature_hashes["validation"], feature_hashes["test"]).size),
    }
    check("cross_split_exact_feature_row_overlap", all(count == 0 for count in feature_row_overlaps.values()), json.dumps(feature_row_overlaps))

    failed_checks = [check_result for check_result in checks if not check_result["passed"]]
    if failed_checks:
        print("STAGE 1 — FAIL")
        for failed in failed_checks:
            print(f"FAIL: {failed['name']}: {failed['detail']}")
        return 1

    # All pre-write validation passed.  Only the new Stage 1 SSOT is written.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    artifact_paths: dict[str, Path] = {}
    for name, matrix in split_matrices.items():
        matrix_path = OUTPUT_DIR / f"X_{name}_final.npy"
        np.save(matrix_path, matrix)
        artifact_paths[matrix_path.name] = matrix_path

        unscaled_path = OUTPUT_DIR / f"{name}_input_unscaled.csv"
        split_unscaled[name].to_csv(unscaled_path, index=False, encoding="utf-8")
        artifact_paths[unscaled_path.name] = unscaled_path

        metadata_path = OUTPUT_DIR / f"{name}_metadata.csv"
        split_raw[name].to_csv(metadata_path, index=False, encoding="utf-8")
        artifact_paths[metadata_path.name] = metadata_path

    scaler_path = OUTPUT_DIR / "final_train_scaler.pkl"
    with scaler_path.open("wb") as handle:
        pickle.dump(scaler, handle)
    artifact_paths[scaler_path.name] = scaler_path

    composition = {name: label_summary(dataframe) for name, dataframe in split_raw.items()}
    session_counts = {name: len(session_ids) for name, session_ids in session_sets.items()}
    data_artifact_paths = artifact_paths.copy()
    output_sha256 = {name: sha256_of(path) for name, path in data_artifact_paths.items()}

    # Validate the files that will be handed to the next stage, rather than only
    # the in-memory values used to produce them.
    for name, expected_matrix in split_matrices.items():
        stored_matrix = np.load(OUTPUT_DIR / f"X_{name}_final.npy", allow_pickle=False)
        check(
            f"{name}_saved_matrix_matches_validated_input",
            stored_matrix.dtype == np.float32
            and stored_matrix.shape == expected_matrix.shape
            and np.array_equal(stored_matrix, expected_matrix),
            str(stored_matrix.shape),
        )
        stored_input = pd.read_csv(OUTPUT_DIR / f"{name}_input_unscaled.csv", encoding="utf-8")
        check(
            f"{name}_saved_input_csv_matches_contract",
            list(stored_input.columns) == FEATURE_COLUMNS and len(stored_input) == len(expected_matrix),
            f"rows={len(stored_input)}, columns={list(stored_input.columns)}",
        )
        stored_metadata = pd.read_csv(OUTPUT_DIR / f"{name}_metadata.csv", encoding="utf-8")
        check(
            f"{name}_saved_metadata_preserves_labels_and_session",
            {"session_id", "username", "role", "risk_level", "anomaly_type"}.issubset(stored_metadata.columns)
            and len(stored_metadata) == len(expected_matrix),
            f"rows={len(stored_metadata)}",
        )

    legacy_after = artifact_hashes(protected_roots)
    check(
        "legacy_and_production_artifacts_unchanged",
        legacy_before == legacy_after,
        f"checked_files={len(legacy_before)}",
    )
    # The post-write safety check must be reflected in the persisted validation output.
    if not checks[-1]["passed"]:
        print("STAGE 1 — FAIL")
        print("FAIL: legacy_and_production_artifacts_unchanged")
        return 1
    post_write_failures = [check_result for check_result in checks if not check_result["passed"]]
    if post_write_failures:
        print("STAGE 1 — FAIL")
        for failed in post_write_failures:
            print(f"FAIL: {failed['name']}: {failed['detail']}")
        return 1

    final_metadata = {
        "stage": "STAGE 1",
        "status": "PASS",
        "purpose": "Final VAE dataset SSOT; no retraining performed.",
        "script": relative(Path(__file__)),
        "seed": SEED,
        "source": {
            "raw_dataset": relative(RAW_SOURCE),
            "encoded_unscaled_dataset": relative(ENCODED_SOURCE),
            "encoded_metadata": relative(ENCODED_METADATA),
            "sha256": source_hashes,
        },
        "feature_order": FEATURE_COLUMNS,
        "excluded_from_vae_input": sorted(FORBIDDEN_INPUT_COLUMNS),
        "split_policy": {
            "method": "session-based deterministic split by session_id",
            "normal_only_session_fractions": NORMAL_SESSION_FRACTIONS,
            "anomalous_session_fractions": ANOMALOUS_SESSION_FRACTIONS,
            "normal_session_count": normal_session_count,
            "anomalous_session_count": anomalous_session_count,
            "normal_session_assignments": normal_session_assignments,
            "anomalous_session_assignments": anomalous_session_assignments,
            "all_rows_assigned_once": True,
            "session_overlap": pair_overlaps,
            "feature_row_overlap": feature_row_overlaps,
        },
        "composition": composition,
        "session_counts": session_counts,
        "scaler": {
            "type": "StandardScaler",
            "fit_subset": "train",
            "fit_row_count": int(len(split_unscaled["train"])),
            "fit_anomaly_row_count": train_anomaly_count,
            "path": relative(scaler_path),
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
            "var": scaler.var_.tolist(),
        },
        "outputs": {name: relative(path) for name, path in data_artifact_paths.items()},
        "output_sha256": output_sha256,
        "legacy_artifacts": {"count": len(legacy_before), "unchanged": True},
        "validation": {"checks": checks, "passed": len(checks), "failed": 0},
    }
    metadata_path = OUTPUT_DIR / "final_dataset_metadata.json"
    metadata_path.write_text(json.dumps(final_metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    artifact_paths[metadata_path.name] = metadata_path

    validation_path = OUTPUT_DIR / "validation_results.json"
    validation_path.write_text(
        json.dumps({"status": "PASS", "checks": checks}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    legacy_manifest_path = OUTPUT_DIR / "legacy_artifact_checksums.json"
    legacy_manifest_path.write_text(
        json.dumps(
            {"before": legacy_before, "after": legacy_after, "unchanged": legacy_before == legacy_after},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    REPORT_FILE.write_text(build_report(final_metadata), encoding="utf-8")
    print("STAGE 1 — PASS")
    print(f"SSOT: {relative(OUTPUT_DIR)}")
    print("Rows:", {name: int(mask.sum()) for name, mask in masks.items()})
    print("Sessions:", session_counts)
    print("Validation checks:", len(checks), "PASS / 0 FAIL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
