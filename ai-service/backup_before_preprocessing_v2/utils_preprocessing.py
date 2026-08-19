"""Inference preprocessing identical to the final training feature contract."""

from __future__ import annotations

import ipaddress
import pickle
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from schemas.predict_request import PredictRequest


SERVICE_DIR = Path(__file__).resolve().parents[1]
PREPROCESSED_DIR = SERVICE_DIR / "dataset" / "preprocessed"
SCALER_PATH = PREPROCESSED_DIR / "scaler.pkl"
ENCODERS_PATH = PREPROCESSED_DIR / "label_encoders.pkl"

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
ENCODER_COLUMNS = ("activity", "status", "device")

ACTIVITY_ALIASES = {
    "CREATE_BERKAS": "Input Berkas",
    "INPUT_BERKAS": "Input Berkas",
    "CARI_BERKAS": "Cari Berkas",
    "LIHAT_BERKAS": "Lihat Berkas",
    "LIHAT_PERKARA": "Lihat Perkara",
    "LOGIN": "Login",
    "LOGOUT": "Logout",
    "VERIFIKASI_INTEGRITAS_BERKAS": "Verifikasi",
    "VERIFIKASI": "Verifikasi",
    "DASHBOARD": "Dashboard",
    "KELOLA_USER": "Kelola User",
    "KELOLA_KLASIFIKASI": "Kelola Kode Klasifikasi",
}

STATUS_ALIASES = {
    "SUCCESS": "Berhasil",
    "BERHASIL": "Berhasil",
    "FAILED": "Gagal",
    "GAGAL": "Gagal",
}

DEVICE_ALIASES = {
    "UNKNOWN": "Unknown Device",
    "WEB BROWSER": "PC Windows",
}


@lru_cache(maxsize=1)
def _load_artifacts():
    if not SCALER_PATH.exists() or not ENCODERS_PATH.exists():
        raise FileNotFoundError("Artefak preprocessing final (scaler/label_encoders) tidak ditemukan.")
    with SCALER_PATH.open("rb") as file:
        scaler = pickle.load(file)
    with ENCODERS_PATH.open("rb") as file:
        encoders = pickle.load(file)
    return scaler, encoders


def _encode(encoder, column: str, value: str) -> int:
    classes = list(encoder.classes_)
    if value in classes:
        return int(encoder.transform([value])[0])

    normalized_val = str(value).strip().upper()

    if column == "activity" and normalized_val in ACTIVITY_ALIASES:
        target = ACTIVITY_ALIASES[normalized_val]
        if target in classes:
            return int(encoder.transform([target])[0])

    if column == "status" and normalized_val in STATUS_ALIASES:
        target = STATUS_ALIASES[normalized_val]
        if target in classes:
            return int(encoder.transform([target])[0])

    if column == "device" and normalized_val in DEVICE_ALIASES:
        target = DEVICE_ALIASES[normalized_val]
        if target in classes:
            return int(encoder.transform([target])[0])

    # Case-insensitive / whitespace match against label_encoders.pkl classes
    for cls in classes:
        if cls.lower() == str(value).strip().lower():
            return int(encoder.transform([cls])[0])

    # Default fallback to first class if unrecognised to maintain inference stability
    return 0


def parse_ip_to_integer(ip_str: str) -> int:
    try:
        return int(ipaddress.ip_address(ip_str.strip()))
    except (ValueError, AttributeError):
        return int(ipaddress.ip_address("0.0.0.0"))


def parse_timestamp(waktu_input: str) -> tuple[int, int]:
    """Return (hour, day_of_week) from ISO timestamp or datetime string."""
    try:
        dt = pd.to_datetime(waktu_input)
        return int(dt.hour), int(dt.dayofweek)
    except Exception:
        now = datetime.now()
        return now.hour, now.weekday()


def preprocess_for_inference(payload: PredictRequest) -> np.ndarray:
    """Encode and scale exactly the nine fields used during final training."""
    scaler, encoders = _load_artifacts()

    user_id = int(payload.user_id)
    activity_encoded = _encode(encoders["activity"], "activity", payload.aksi)
    status_encoded = _encode(encoders["status"], "status", payload.status)
    device_encoded = _encode(encoders["device"], "device", payload.device)
    ip_integer = parse_ip_to_integer(payload.ip_address)
    duration_ms = float(payload.durasi_ms)
    object_count = float(payload.jumlah_objek)
    hour, day_of_week = parse_timestamp(payload.waktu)

    features_df = pd.DataFrame(
        [[
            user_id,
            activity_encoded,
            status_encoded,
            device_encoded,
            ip_integer,
            duration_ms,
            object_count,
            hour,
            day_of_week,
        ]],
        columns=list(FEATURE_COLUMNS),
    )

    scaled_values = scaler.transform(features_df)
    return scaled_values.astype(np.float32)
