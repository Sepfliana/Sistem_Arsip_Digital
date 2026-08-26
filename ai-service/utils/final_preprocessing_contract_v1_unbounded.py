"""Stage 2 single preprocessing contract for the final VAE dataset.

The module deliberately contains the only raw-record transformation used by
both the Stage 2 training preparation and its inference adapter.  It does not
import a model, calculate a score, or make a deployment decision.
"""

from __future__ import annotations

import ipaddress
import pickle
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import OrdinalEncoder, StandardScaler


FEATURE_COLUMNS = (
    "user_id",
    "activity",
    "status",
    "device",
    "ip_address",
    "duration_ms",
    "object_count",
    "hour",
    "day_of_week",
)
CATEGORICAL_COLUMNS = ("activity", "status", "device")
TIMEZONE = "Asia/Jakarta"
UNKNOWN_CATEGORY_CODE = -1

ENCODER_FILENAME = "categorical_encoder.pkl"
SCALER_FILENAME = "train_only_scaler.pkl"
CONTRACT_FILENAME = "feature_contract.json"


def _as_mapping(record: Mapping[str, Any] | Any) -> Mapping[str, Any]:
    if isinstance(record, Mapping):
        return record
    if hasattr(record, "model_dump"):
        return record.model_dump()
    raise TypeError("Record harus berupa mapping atau model Pydantic.")


def _value(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in record and record[name] is not None:
            return record[name]
    raise ValueError(f"Field wajib tidak tersedia: {' / '.join(names)}")


def _text(record: Mapping[str, Any], *names: str) -> str:
    value = str(_value(record, *names)).strip()
    if not value:
        raise ValueError(f"Field teks tidak boleh kosong: {' / '.join(names)}")
    return value


def _number(record: Mapping[str, Any], names: tuple[str, ...], *, minimum: float | None = None) -> float:
    try:
        value = float(_value(record, *names))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Nilai numerik tidak valid untuk {' / '.join(names)}.") from error
    if not np.isfinite(value):
        raise ValueError(f"Nilai numerik harus finite untuk {' / '.join(names)}.")
    if minimum is not None and value < minimum:
        raise ValueError(f"Nilai numerik tidak boleh < {minimum} untuk {' / '.join(names)}.")
    return value


def parse_timestamp_wib(value: Any) -> tuple[int, int]:
    """Return WIB hour and Monday=0 day of week without shifting naive WIB time.

    A timezone-naive timestamp supplied by the audit-log source represents WIB
    already, so it is used as local time.  Only an explicitly timezone-aware
    timestamp is converted into Asia/Jakarta.
    """
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Timestamp tidak valid: {value!r}.") from error
    if pd.isna(timestamp):
        raise ValueError("Timestamp tidak boleh kosong/NaT.")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(TIMEZONE).tz_localize(None)
    return int(timestamp.hour), int(timestamp.dayofweek)


def ipv4_to_integer(value: Any) -> float:
    """Convert IPv4 to its unsigned 32-bit integer representation exactly."""
    try:
        parsed = ipaddress.ip_address(str(value).strip())
    except ValueError as error:
        raise ValueError(f"IP address tidak valid: {value!r}.") from error
    if parsed.version != 4:
        raise ValueError(f"Kontrak final hanya mendukung IPv4, diterima IPv{parsed.version}: {value!r}.")
    return float(int(parsed))


def fit_categorical_encoder(training_records: Iterable[Mapping[str, Any] | Any]) -> OrdinalEncoder:
    """Fit the sole categorical encoder on training records only.

    Unknown categories are represented as -1 during transform.  This is an
    explicit behaviour of the *same fitted encoder*, never a second inference
    encoder or a fallback fit.  It preserves the nine-dimensional VAE input and
    allows labelled evaluation anomalies to remain transformable.
    """
    records = [_as_mapping(record) for record in training_records]
    if not records:
        raise ValueError("Training records kosong; encoder tidak dapat di-fit.")
    categories = pd.DataFrame(
        [
            {
                "activity": _text(record, "activity", "aksi"),
                "status": _text(record, "status"),
                "device": _text(record, "device"),
            }
            for record in records
        ],
        columns=list(CATEGORICAL_COLUMNS),
    )
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=UNKNOWN_CATEGORY_CODE,
        dtype=np.float64,
    )
    encoder.fit(categories)
    return encoder


def records_to_unscaled_matrix(
    records: Iterable[Mapping[str, Any] | Any], categorical_encoder: OrdinalEncoder
) -> np.ndarray:
    """Apply the final raw-to-nine-feature transformation using a fitted encoder."""
    source_records = [_as_mapping(record) for record in records]
    if not source_records:
        return np.empty((0, len(FEATURE_COLUMNS)), dtype=np.float64)
    category_frame = pd.DataFrame(
        [
            {
                "activity": _text(record, "activity", "aksi"),
                "status": _text(record, "status"),
                "device": _text(record, "device"),
            }
            for record in source_records
        ],
        columns=list(CATEGORICAL_COLUMNS),
    )
    category_values = categorical_encoder.transform(category_frame)
    rows: list[list[float]] = []
    for record, categorical in zip(source_records, category_values, strict=True):
        hour, day_of_week = parse_timestamp_wib(_value(record, "timestamp", "waktu"))
        rows.append(
            [
                _number(record, ("user_id",), minimum=0),
                float(categorical[0]),
                float(categorical[1]),
                float(categorical[2]),
                ipv4_to_integer(_value(record, "ip_address")),
                _number(record, ("duration_ms", "durasi_ms"), minimum=0),
                _number(record, ("object_count", "jumlah_objek"), minimum=0),
                float(hour),
                float(day_of_week),
            ]
        )
    matrix = np.asarray(rows, dtype=np.float64)
    if matrix.shape != (len(source_records), len(FEATURE_COLUMNS)) or not np.isfinite(matrix).all():
        raise ValueError("Matrix preprocessing tidak valid (shape/NaN/Inf).")
    return matrix


def scale_matrix(unscaled_matrix: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    values = np.asarray(unscaled_matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError(f"Matrix harus berbentuk (n, 9), diterima {values.shape}.")
    return scaler.transform(values).astype(np.float32)


def load_final_artifacts(artifact_dir: Path) -> tuple[OrdinalEncoder, StandardScaler]:
    encoder_path = artifact_dir / ENCODER_FILENAME
    scaler_path = artifact_dir / SCALER_FILENAME
    if not encoder_path.exists() or not scaler_path.exists():
        raise FileNotFoundError("Artifact Stage 2 categorical encoder/scaler tidak ditemukan.")
    with encoder_path.open("rb") as handle:
        encoder = pickle.load(handle)
    with scaler_path.open("rb") as handle:
        scaler = pickle.load(handle)
    if not isinstance(encoder, OrdinalEncoder) or not isinstance(scaler, StandardScaler):
        raise TypeError("Jenis artifact preprocessing Stage 2 tidak sesuai kontrak.")
    if getattr(scaler, "n_features_in_", None) != len(FEATURE_COLUMNS):
        raise ValueError("Scaler Stage 2 tidak memiliki sembilan fitur.")
    return encoder, scaler


def preprocess_for_inference(record: Mapping[str, Any] | Any, artifact_dir: Path) -> np.ndarray:
    """Inference adapter: load fitted artifacts and transform only, never fit."""
    encoder, scaler = load_final_artifacts(artifact_dir)
    unscaled = records_to_unscaled_matrix([record], encoder)
    return scale_matrix(unscaled, scaler)
