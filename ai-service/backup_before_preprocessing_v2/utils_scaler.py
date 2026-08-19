"""Utility scaling fitur numerik audit log."""

from typing import Iterable, Tuple

import joblib
import pandas as pd
from sklearn.preprocessing import StandardScaler


def fit_scale_columns(
    dataframe: pd.DataFrame,
    columns: Iterable[str],
) -> Tuple[pd.DataFrame, StandardScaler]:
    """Melatih StandardScaler dan mengubah kolom numerik yang dipilih."""
    scaled = dataframe.copy()
    selected_columns = list(columns)
    scaler = StandardScaler()
    scaled[selected_columns] = scaler.fit_transform(scaled[selected_columns])

    return scaled, scaler


def transform_scaled_columns(
    dataframe: pd.DataFrame,
    columns: Iterable[str],
    scaler: StandardScaler,
) -> pd.DataFrame:
    """Mengubah kolom numerik memakai StandardScaler tersimpan."""
    scaled = dataframe.copy()
    selected_columns = list(columns)
    scaled[selected_columns] = scaler.transform(scaled[selected_columns])

    return scaled


def save_scaler(scaler: StandardScaler, path: str) -> None:
    """Menyimpan scaler ke file pickle/joblib."""
    joblib.dump(scaler, path)


def load_scaler(path: str) -> StandardScaler:
    """Memuat scaler dari file pickle/joblib."""
    return joblib.load(path)
