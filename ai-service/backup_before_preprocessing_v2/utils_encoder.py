"""Utility encoding fitur kategorikal audit log."""

from typing import Dict, Iterable

import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder


EncoderMap = Dict[str, LabelEncoder]


def fit_label_encoders(dataframe: pd.DataFrame, columns: Iterable[str]) -> EncoderMap:
    """Melatih LabelEncoder untuk setiap kolom kategorikal."""
    encoders: EncoderMap = {}

    for column in columns:
        encoder = LabelEncoder()
        dataframe[column] = encoder.fit_transform(dataframe[column].astype(str))
        encoders[column] = encoder

    return encoders


def transform_with_encoders(dataframe: pd.DataFrame, encoders: EncoderMap) -> pd.DataFrame:
    """Mengubah nilai kategorikal memakai encoder tersimpan.

    Nilai kategori baru yang belum pernah dilihat saat training diberi nilai -1.
    Ini membuat endpoint prediksi tetap stabil untuk data produksi baru.
    """
    transformed = dataframe.copy()

    for column, encoder in encoders.items():
        class_mapping = {value: index for index, value in enumerate(encoder.classes_)}
        transformed[column] = (
            transformed[column]
            .astype(str)
            .map(class_mapping)
            .fillna(-1)
            .astype(int)
        )

    return transformed


def save_encoders(encoders: EncoderMap, path: str) -> None:
    """Menyimpan encoder ke file pickle/joblib."""
    joblib.dump(encoders, path)


def load_encoders(path: str) -> EncoderMap:
    """Memuat encoder dari file pickle/joblib."""
    return joblib.load(path)
