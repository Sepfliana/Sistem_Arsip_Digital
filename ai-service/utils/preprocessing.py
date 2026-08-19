"""Inference preprocessing fully synchronized with the single source of truth contract."""

from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from schemas.predict_request import PredictRequest
from utils.preprocessing_contract import (
    FEATURE_COLUMNS,
    map_canonical_activity,
    map_canonical_status,
    map_ip_category,
    parse_timestamp_wib,
    parse_user_agent_device,
    process_record,
    transform_numeric_features,
)

SERVICE_DIR = Path(__file__).resolve().parents[1]
PREPROCESSED_DIR = SERVICE_DIR / "dataset" / "preprocessed"
SCALER_PATH = PREPROCESSED_DIR / "scaler.pkl"
ENCODERS_PATH = PREPROCESSED_DIR / "label_encoders.pkl"


@lru_cache(maxsize=1)
def _load_artifacts():
    if not SCALER_PATH.exists() or not ENCODERS_PATH.exists():
        raise FileNotFoundError("Artefak preprocessing final (scaler/label_encoders) tidak ditemukan.")
    with SCALER_PATH.open("rb") as file:
        scaler = pickle.load(file)
    with ENCODERS_PATH.open("rb") as file:
        encoders = pickle.load(file)
    return scaler, encoders


def _encode_canonical_value(encoder, value: str) -> int:
    """Encode canonical value using deterministic LabelEncoder, handling UNKNOWN safely."""
    classes = list(encoder.classes_)
    if value in classes:
        return int(encoder.transform([value])[0])

    if "UNKNOWN" in classes:
        return int(encoder.transform(["UNKNOWN"])[0])

    for cls in classes:
        if cls.lower() == str(value).strip().lower():
            return int(encoder.transform([cls])[0])

    return 0


def preprocess_for_inference(payload: PredictRequest) -> np.ndarray:
    """Encode and scale exactly the nine fields using the shared preprocessing contract."""
    scaler, encoders = _load_artifacts()

    rec = process_record({
        "user_id": payload.user_id,
        "aksi": payload.aksi,
        "status": payload.status,
        "device": payload.device,
        "ip_address": payload.ip_address,
        "durasi_ms": payload.durasi_ms,
        "jumlah_objek": payload.jumlah_objek,
        "waktu": payload.waktu,
    })

    activity_encoded = _encode_canonical_value(encoders["activity"], rec["activity"])
    status_encoded = _encode_canonical_value(encoders["status"], rec["status"])
    device_encoded = _encode_canonical_value(encoders["device"], rec["device"])
    ip_encoded = _encode_canonical_value(encoders["ip_address"], rec["ip_address"]) if "ip_address" in encoders else 0

    features_df = pd.DataFrame(
        [[
            rec["user_id"],
            activity_encoded,
            status_encoded,
            device_encoded,
            ip_encoded,
            rec["duration_ms"],
            rec["object_count"],
            rec["hour"],
            rec["day_of_week"],
        ]],
        columns=list(FEATURE_COLUMNS),
    )

    scaled_values = scaler.transform(features_df)
    return scaled_values.astype(np.float32)
