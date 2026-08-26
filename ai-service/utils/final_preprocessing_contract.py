"""The single Stage 2 preprocessing contract used by final VAE training/inference.

Raw IPv4 is always converted to the unsigned 32-bit integer required by the
thesis.  The train-only StandardScaler output for IP and user_id is bounded to
[-3, 3]: this prevents a narrow training range from turning an out-of-domain
value into a multi-sigma outlier.  The bound is label-free and applied
identically to every split and inference record.
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
    "user_id", "activity", "status", "device", "ip_address",
    "duration_ms", "object_count", "hour", "day_of_week",
)
CATEGORICAL_COLUMNS = ("activity", "status", "device")
TIMEZONE = "Asia/Jakarta"
UNKNOWN_CATEGORY_CODE = -1
IP_FEATURE_INDEX = FEATURE_COLUMNS.index("ip_address")
USERID_FEATURE_INDEX = FEATURE_COLUMNS.index("user_id")
IP_ZSCORE_BOUNDS = (-3.0, 3.0)

# Training-mean IP used when the actual IP is unknown/unavailable.
# Training IPs are all in 192.168.1.0/24 (mean = 192.168.1.122, uint32 = 3232235898).
# This value produces a z-score of exactly 0.0 after StandardScaler, which is the
# most "normal" representation and avoids introducing artificial anomaly signal.
TRAINING_MEAN_IP = "192.168.1.122"
TRAINING_MEAN_IP_UINT32 = 3232235898.0

ENCODER_FILENAME = "categorical_encoder.pkl"
SCALER_FILENAME = "train_only_scaler.pkl"
CONTRACT_FILENAME = "feature_contract.json"

# ── Backend → Training label mappings ──────────────────────────────────────
# The training encoder was fit on 10 Indonesian activity labels, 2 status
# labels, and 5 device labels.  The backend sends English/technical values.
# These mappings make inference input consistent with training representation.
#
# Training activity classes (ordinal): Cari Berkas(0), Dashboard(1),
#   Input Berkas(2), Kelola Kode Klasifikasi(3), Kelola User(4),
#   Lihat Berkas(5), Lihat Perkara(6), Login(7), Logout(8), Verifikasi(9)
# Training status classes: Berhasil(0), Gagal(1)
# Training device classes: Android(0), Laptop Windows(1), PC Windows(2),
#   Windows(3), iPhone(4)

ACTIVITY_ALIASES: dict[str, str] = {
    "LOGIN_SUCCESS": "Login",
    "LOGOUT": "Logout",
    "ACCESS_BERKAS_FILE": "Lihat Berkas",
    "CREATE_BERKAS": "Input Berkas",
    "UPDATE_BERKAS": "Input Berkas",
    "DELETE_BERKAS": "Input Berkas",
    "PERUBAHAN_STATUS_ARSIP": "Input Berkas",
    "RETENSI_INAKTIF": "Input Berkas",
    "CREATE_USER": "Kelola User",
    "UPDATE_USER": "Kelola User",
    "DELETE_USER": "Kelola User",
    "SETUP_2FA_GENERATE": "Kelola User",
    "AKTIVASI_OTP": "Kelola User",
    "DISABLE_2FA_EMAIL_CHANGED": "Kelola User",
    "REQUEST_RESET_PASSWORD": "Kelola User",
    "RESET_PASSWORD": "Kelola User",
    "CREATE_LEMARI": "Kelola Kode Klasifikasi",
    "UPDATE_LEMARI": "Kelola Kode Klasifikasi",
    "DELETE_LEMARI": "Kelola Kode Klasifikasi",
    "CREATE_RAK": "Kelola Kode Klasifikasi",
    "UPDATE_RAK": "Kelola Kode Klasifikasi",
    "DELETE_RAK": "Kelola Kode Klasifikasi",
    "VERIFIKASI_INTEGRITAS_BERKAS": "Verifikasi",
    "EXPORT_VERIFICATION_REPORT": "Verifikasi",
    "POTENSI_ANOMALI_HASH_BERKAS": "Verifikasi",
    "KEPUTUSAN_ANOMALI_DITERIMA": "Verifikasi",
    "KEPUTUSAN_ANOMALI_OVERRIDE": "Verifikasi",
    "KEPUTUSAN_ANOMALI_SELESAI": "Verifikasi",
    "CREATE_PERKARA": "Lihat Perkara",
    "UPDATE_PERKARA": "Lihat Perkara",
    "DELETE_PERKARA": "Lihat Perkara",
    "AJUKAN_PEMINJAMAN": "Input Berkas",
    "SETUJUI_PEMINJAMAN": "Input Berkas",
    "PINJAM": "Input Berkas",
    "PENGEMBALIAN": "Input Berkas",
    "DELETE_PEMINJAMAN": "Input Berkas",
    "UPDATE_PEMINJAMAN": "Input Berkas",
    "TOLAK_PEMINJAMAN": "Input Berkas",
}

STATUS_ALIASES: dict[str, str] = {
    "SUCCESS": "Berhasil",
    "VALID": "Berhasil",
    "FAILED": "Gagal",
    "GAGAL": "Gagal",
    "ERROR": "Gagal",
    "HASH TIDAK SESUAI": "Gagal",
}


def _normalize_device(raw: str) -> str:
    """Map a raw device/User-Agent string to one of the five training classes.

    Training device classes: Android, Laptop Windows, PC Windows, Windows,
    iPhone.  The User-Agent is matched against the training classes using
    substring checks.  Unrecognised values (Mac, Linux, empty, unknown) fall
    back to "Windows" — the most common training class and the most general
    Windows category — because the system is a web application accessed from
    browsers and the training distribution is dominated by Windows clients.
    """
    upper = raw.upper()
    if "IPHONE" in upper or "IPAD" in upper or "IOS" in upper:
        return "iPhone"
    if "ANDROID" in upper:
        return "Android"
    if "WINDOWS" in upper or "WIN64" in upper or "WIN32" in upper:
        return "Windows"
    return "Windows"


def _normalize_activity(raw: str) -> str:
    """Map a backend aksi value to a training activity label."""
    upper = raw.strip().upper()
    if upper in ACTIVITY_ALIASES:
        return ACTIVITY_ALIASES[upper]
    title = raw.strip()
    training_classes = [
        "Cari Berkas", "Dashboard", "Input Berkas",
        "Kelola Kode Klasifikasi", "Kelola User",
        "Lihat Berkas", "Lihat Perkara", "Login", "Logout", "Verifikasi",
    ]
    if title in training_classes:
        return title
    for cls in training_classes:
        if cls.lower() == title.lower():
            return cls
    return title


def _normalize_status(raw: str) -> str:
    """Map a backend status value to a training status label."""
    upper = raw.strip().upper()
    if upper in STATUS_ALIASES:
        return STATUS_ALIASES[upper]
    if raw.strip() in ("Berhasil", "Gagal"):
        return raw.strip()
    return raw.strip()


def _normalize_backend_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of the record with backend values mapped to training labels.

    This is the single place where the translation from backend representation
    (English aksi/status, raw User-Agent) to training representation
    (Indonesian labels) occurs.  Numeric and temporal fields pass through
    unchanged.
    """
    normalized = dict(record)
    raw_activity = _text(record, "activity", "aksi")
    raw_status = _text(record, "status")
    raw_device = _text(record, "device")
    normalized["activity"] = _normalize_activity(raw_activity)
    normalized["status"] = _normalize_status(raw_status)
    normalized["device"] = _normalize_device(raw_device)
    return normalized


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


def _number(record: Mapping[str, Any], names: tuple[str, ...], minimum: float = 0.0) -> float:
    try:
        value = float(_value(record, *names))
    except (TypeError, ValueError) as error:
        raise ValueError(f"Nilai numerik tidak valid untuk {' / '.join(names)}.") from error
    if not np.isfinite(value) or value < minimum:
        raise ValueError(f"Nilai numerik harus finite dan >= {minimum} untuk {' / '.join(names)}.")
    return value


def parse_timestamp_wib(value: Any) -> tuple[int, int]:
    """Derive hour/day without treating a naive WIB timestamp as UTC."""
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
    """Return the raw unsigned IPv4 32-bit integer.

    For unknown/invalid/missing IPs, falls back to the training-mean IP
    (192.168.1.122 = 3232235898) which produces z-score 0.0 after scaling.
    """
    raw = str(value).strip() if value is not None else ""
    if not raw or raw.lower() in ("unknown", "none", "null", ""):
        return TRAINING_MEAN_IP_UINT32
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        return TRAINING_MEAN_IP_UINT32
    if ip.version != 4:
        return TRAINING_MEAN_IP_UINT32
    return float(int(ip))


def fit_categorical_encoder(training_records: Iterable[Mapping[str, Any] | Any]) -> OrdinalEncoder:
    records = [_as_mapping(record) for record in training_records]
    if not records:
        raise ValueError("Training records kosong; encoder tidak dapat di-fit.")
    categories = pd.DataFrame([
        {"activity": _text(record, "activity", "aksi"), "status": _text(record, "status"), "device": _text(record, "device")}
        for record in records
    ], columns=list(CATEGORICAL_COLUMNS))
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=UNKNOWN_CATEGORY_CODE, dtype=np.float64)
    encoder.fit(categories)
    return encoder


def records_to_unscaled_matrix(records: Iterable[Mapping[str, Any] | Any], categorical_encoder: OrdinalEncoder) -> np.ndarray:
    source = [_as_mapping(record) for record in records]
    if not source:
        return np.empty((0, len(FEATURE_COLUMNS)), dtype=np.float64)
    normalized = [_normalize_backend_record(record) for record in source]
    category_frame = pd.DataFrame([
        {"activity": _text(record, "activity", "aksi"), "status": _text(record, "status"), "device": _text(record, "device")}
        for record in normalized
    ], columns=list(CATEGORICAL_COLUMNS))
    categories = categorical_encoder.transform(category_frame)
    rows: list[list[float]] = []
    for record, category in zip(normalized, categories, strict=True):
        hour, day_of_week = parse_timestamp_wib(_value(record, "timestamp", "waktu"))
        rows.append([
            _number(record, ("user_id",)), float(category[0]), float(category[1]), float(category[2]),
            ipv4_to_integer(_value(record, "ip_address")), _number(record, ("duration_ms", "durasi_ms")),
            _number(record, ("object_count", "jumlah_objek")), float(hour), float(day_of_week),
        ])
    result = np.asarray(rows, dtype=np.float64)
    if result.shape != (len(source), len(FEATURE_COLUMNS)) or not np.isfinite(result).all():
        raise ValueError("Matrix preprocessing tidak valid (shape/NaN/Inf).")
    return result


def scale_matrix(unscaled_matrix: np.ndarray, scaler: StandardScaler) -> np.ndarray:
    """Apply train-only scaler then bounded z-score for IP and user_id."""
    values = np.asarray(unscaled_matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(FEATURE_COLUMNS):
        raise ValueError(f"Matrix harus berbentuk (n, 9), diterima {values.shape}.")
    scaled = scaler.transform(values)
    scaled[:, IP_FEATURE_INDEX] = np.clip(scaled[:, IP_FEATURE_INDEX], *IP_ZSCORE_BOUNDS)
    scaled[:, USERID_FEATURE_INDEX] = np.clip(scaled[:, USERID_FEATURE_INDEX], *IP_ZSCORE_BOUNDS)
    return scaled.astype(np.float32)


def load_final_artifacts(artifact_dir: Path) -> tuple[OrdinalEncoder, StandardScaler]:
    encoder_path, scaler_path = artifact_dir / ENCODER_FILENAME, artifact_dir / SCALER_FILENAME
    if not encoder_path.exists() or not scaler_path.exists():
        raise FileNotFoundError("Artifact encoder/scaler preprocessing final tidak ditemukan.")
    with encoder_path.open("rb") as file:
        encoder = pickle.load(file)
    with scaler_path.open("rb") as file:
        scaler = pickle.load(file)
    if not isinstance(encoder, OrdinalEncoder) or not isinstance(scaler, StandardScaler):
        raise TypeError("Jenis artifact preprocessing final tidak sesuai kontrak.")
    if getattr(scaler, "n_features_in_", None) != len(FEATURE_COLUMNS):
        raise ValueError("Scaler final tidak memiliki sembilan fitur.")
    return encoder, scaler


def preprocess_for_inference(record: Mapping[str, Any] | Any, artifact_dir: Path) -> np.ndarray:
    """Transform a raw record using only fitted final artifacts; never fit."""
    encoder, scaler = load_final_artifacts(artifact_dir)
    return scale_matrix(records_to_unscaled_matrix([record], encoder), scaler)
