"""Pipeline preprocessing dataset audit log untuk training VAE."""

from __future__ import annotations

import ipaddress
import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder, StandardScaler


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "dataset" / "generator" / "raw" / "audit_log_dataset.csv"
OUTPUT_DIR = BASE_DIR / "dataset" / "preprocessed"
X_TRAIN_FILE = OUTPUT_DIR / "X_train.npy"
ENCODERS_FILE = OUTPUT_DIR / "label_encoders.pkl"
SCALER_FILE = OUTPUT_DIR / "scaler.pkl"
METADATA_FILE = OUTPUT_DIR / "preprocessing_metadata.json"

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
ENCODER_COLUMNS = ["activity", "status", "device"]


def ip_to_integer(value: str) -> int:
    return int(ipaddress.ip_address(value))


def preprocess_audit_log() -> np.ndarray:
    dataframe = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    dataframe["timestamp"] = pd.to_datetime(dataframe["timestamp"])
    dataframe["hour"] = dataframe["timestamp"].dt.hour
    dataframe["day_of_week"] = dataframe["timestamp"].dt.dayofweek

    dataframe = dataframe.drop(
        columns=["timestamp", "session_id", "username", "role", "risk_level", "anomaly_type"]
    )

    label_encoders = {}
    for column in ENCODER_COLUMNS:
        encoder = LabelEncoder()
        dataframe[column] = encoder.fit_transform(dataframe[column])
        label_encoders[column] = encoder

    dataframe["ip_address"] = dataframe["ip_address"].apply(ip_to_integer)
    features = dataframe[FEATURE_COLUMNS]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(features).astype(np.float64)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(X_TRAIN_FILE, X_train)
    with ENCODERS_FILE.open("wb") as file:
        pickle.dump(label_encoders, file)
    with SCALER_FILE.open("wb") as file:
        pickle.dump(scaler, file)
    with METADATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            {
                "dataset_rows": int(len(dataframe)),
                "feature_count": len(FEATURE_COLUMNS),
                "feature_names": FEATURE_COLUMNS,
                "scaler": "StandardScaler",
                "encoder_columns": ENCODER_COLUMNS,
                "created_at": datetime.now().isoformat(),
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    return X_train


if __name__ == "__main__":
    preprocess_audit_log()
