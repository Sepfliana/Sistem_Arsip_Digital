"""Konfigurasi utama AI Service untuk deteksi anomali audit log."""

from pathlib import Path
from typing import Dict, Union

from dotenv import load_dotenv

import os


# Root folder AI Service.
BASE_DIR = Path(__file__).resolve().parent

# Memuat konfigurasi dari file .env di folder ai-service.
load_dotenv(BASE_DIR / ".env", override=True)


# Konfigurasi server FastAPI.
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))


# Konfigurasi PostgreSQL. Password tidak diberi default agar tidak hardcoded.
HOST = os.getenv("HOST") or os.getenv("DB_HOST", "localhost")
PORT = int(os.getenv("PORT") or os.getenv("DB_PORT", "5432"))
DATABASE = os.getenv("DATABASE") or os.getenv("DB_NAME", "sistem_arsip_digital")
USER = os.getenv("USER") or os.getenv("DB_USER", "postgres")
PASSWORD = os.getenv("PASSWORD") or os.getenv("DB_PASSWORD", "")


def resolve_service_path(value: Union[str, Path]) -> Path:
    """Mengubah path relatif dari .env menjadi path absolut di folder ai-service."""
    path = Path(value)
    if path.is_absolute():
        return path

    return BASE_DIR / path


# Konfigurasi path artefak model dan dataset.
DATASET_PATH = resolve_service_path(os.getenv("DATASET_PATH", "dataset/dataset_vae.csv"))
MODEL_PATH = resolve_service_path(os.getenv("MODEL_PATH", "model/vae_model.keras"))
MODEL_SPEC_PATH = resolve_service_path(os.getenv("MODEL_SPEC_PATH", "model/model_spec.json"))
SCALER_PATH = resolve_service_path(os.getenv("SCALER_PATH", "model/scaler.pkl"))
ENCODERS_PATH = resolve_service_path(os.getenv("ENCODERS_PATH", "model/encoders.pkl"))
THRESHOLD_PATH = resolve_service_path(os.getenv("THRESHOLD_PATH", "model/threshold.json"))


# Konfigurasi log.
TRAINING_LOG_PATH = BASE_DIR / "logs" / "training.log"
PREDICTION_LOG_PATH = BASE_DIR / "logs" / "prediction.log"
TRAINING_HISTORY_PATH = BASE_DIR / "training" / "history.json"
TENSORBOARD_LOG_DIR = BASE_DIR / "training" / "tensorboard"


# Konfigurasi training VAE.
LATENT_DIM = int(os.getenv("LATENT_DIM", "8"))
EPOCHS = int(os.getenv("EPOCHS", "100"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "32"))
VALIDATION_SPLIT = float(os.getenv("VALIDATION_SPLIT", "0.2"))
RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))


def get_database_config() -> Dict[str, object]:
    """Mengembalikan konfigurasi database dalam bentuk dictionary."""
    return {
        "host": HOST,
        "port": PORT,
        "database": DATABASE,
        "user": USER,
        "password": PASSWORD,
    }
