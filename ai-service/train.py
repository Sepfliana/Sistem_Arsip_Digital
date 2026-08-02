"""Pipeline training Variational Autoencoder untuk audit log."""

from __future__ import annotations

import json
import csv
from typing import Any, Dict, Tuple

import numpy as np
import tensorflow as tf
from tensorflow import keras

try:
    from config import DATASET_PATH, MODEL_PATH, THRESHOLD_PATH, TRAINING_HISTORY_PATH
except ModuleNotFoundError as error:
    if error.name != "dotenv":
        raise

    BASE_DIR = __file__
    from pathlib import Path

    SERVICE_DIR = Path(BASE_DIR).resolve().parent
    DATASET_PATH = SERVICE_DIR / "dataset" / "dataset_vae.csv"
    MODEL_PATH = SERVICE_DIR / "model" / "vae_model.keras"
    THRESHOLD_PATH = SERVICE_DIR / "model" / "threshold.json"
    TRAINING_HISTORY_PATH = SERVICE_DIR / "training" / "history.json"

from utils.logging_utils import setup_file_logger
from utils.vae import build_vae, load_model_spec


TRAINING_LOG_PATH = TRAINING_HISTORY_PATH.parents[1] / "logs" / "training.log"


def load_dataset() -> Tuple[list[str], np.ndarray]:
    """Membaca dataset VAE dari DATASET_PATH tanpa membuat dataset baru."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset tidak ditemukan di {DATASET_PATH}. "
            "Jalankan preprocessing Sprint 1 terlebih dahulu."
        )

    with DATASET_PATH.open("r", encoding="utf-8", newline="") as dataset_file:
        reader = csv.reader(dataset_file)
        header = next(reader, None)

    if not header:
        raise ValueError("Dataset training tidak memiliki header feature.")

    values = np.genfromtxt(
        DATASET_PATH,
        delimiter=",",
        skip_header=1,
        dtype=np.float32,
    )

    if values.ndim == 1 and values.size > 0:
        values = values.reshape(1, -1)

    return header, values


def validate_dataset(
    feature_names: list[str],
    values: np.ndarray,
    expected_feature_count: int,
) -> None:
    """Memastikan dataset siap digunakan untuk training VAE."""
    if values.size == 0:
        raise ValueError("Dataset training kosong.")

    if len(feature_names) != expected_feature_count or values.shape[1] != expected_feature_count:
        raise ValueError(
            "Jumlah feature dataset tidak sesuai model_spec: "
            f"{values.shape[1]} != {expected_feature_count}"
        )

    if np.isnan(values).any():
        raise ValueError("Dataset training masih memiliki nilai NaN.")

    if not np.issubdtype(values.dtype, np.number):
        raise ValueError("Seluruh feature dataset harus numeric.")

    if len(values) < 2:
        raise ValueError("Dataset minimal harus memiliki 2 baris untuk train/validation split.")


def split_train_validation(
    values: np.ndarray,
    validation_split: float,
    random_seed: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """Memisahkan data menjadi train dan validation sesuai model_spec."""
    if not 0 < validation_split < 1:
        raise ValueError("validation_split harus berada di antara 0 dan 1.")

    random_generator = np.random.default_rng(random_seed)
    shuffled_indices = random_generator.permutation(len(values))
    validation_size = max(1, int(round(len(values) * validation_split)))

    if validation_size >= len(values):
        validation_size = len(values) - 1

    validation_indices = shuffled_indices[:validation_size]
    train_indices = shuffled_indices[validation_size:]

    return values[train_indices], values[validation_indices]


def build_callbacks() -> list[keras.callbacks.Callback]:
    """Membuat callback training VAE untuk early stopping dan checkpoint."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    return [
        keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=10,
            restore_best_weights=True,
        ),
        keras.callbacks.ModelCheckpoint(
            filepath=MODEL_PATH,
            monitor="val_loss",
            save_best_only=True,
        ),
    ]


def calculate_reconstruction_errors(model: keras.Model, values: np.ndarray) -> np.ndarray:
    """Menghitung MSE antara input dan hasil rekonstruksi model."""
    reconstructed = model(values, training=False).numpy()
    return np.mean(np.square(values - reconstructed), axis=1)


def save_threshold(reconstruction_errors: np.ndarray) -> Dict[str, float]:
    """Menghitung dan menyimpan threshold anomali dari data training."""
    mean_error = float(np.mean(reconstruction_errors))
    std_error = float(np.std(reconstruction_errors))
    threshold = mean_error + (3 * std_error)
    threshold_payload = {
        "threshold": float(threshold),
        "mean_error": mean_error,
        "std_error": std_error,
    }

    THRESHOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with THRESHOLD_PATH.open("w", encoding="utf-8") as threshold_file:
        json.dump(threshold_payload, threshold_file, indent=4)

    return threshold_payload


def save_history(history: keras.callbacks.History) -> Dict[str, Any]:
    """Menyimpan history training minimal untuk analisis eksperimen."""
    history_payload = {
        "loss": history.history.get("loss", []),
        "val_loss": history.history.get("val_loss", []),
        "reconstruction_loss": history.history.get("reconstruction_loss", []),
        "kl_loss": history.history.get("kl_loss", []),
    }

    TRAINING_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRAINING_HISTORY_PATH.open("w", encoding="utf-8") as history_file:
        json.dump(history_payload, history_file, indent=4)

    return history_payload


def run_training() -> Dict[str, Any]:
    """Menjalankan training VAE, menyimpan model terbaik, threshold, dan history."""
    model_spec = load_model_spec()
    tf.keras.utils.set_random_seed(int(model_spec["random_seed"]))

    feature_names, values = load_dataset()
    validate_dataset(
        feature_names,
        values,
        expected_feature_count=int(model_spec["input_feature_count"]),
    )

    train_values, validation_values = split_train_validation(
        values,
        validation_split=float(model_spec["validation_split"]),
        random_seed=int(model_spec["random_seed"]),
    )

    _, _, vae_model = build_vae()
    history = vae_model.fit(
        train_values,
        epochs=int(model_spec["epochs"]),
        batch_size=int(model_spec["batch_size"]),
        validation_data=(validation_values,),
        callbacks=build_callbacks(),
        verbose=1,
    )

    reconstruction_errors = calculate_reconstruction_errors(vae_model, train_values)
    threshold_payload = save_threshold(reconstruction_errors)
    history_payload = save_history(history)

    best_validation_loss = float(min(history_payload["val_loss"]))
    epoch_used = len(history_payload["loss"])

    logger = setup_file_logger("training", TRAINING_LOG_PATH)
    logger.info(
        "training_finished | rows=%s | epoch_used=%s | best_val_loss=%s | threshold=%s",
        len(values),
        epoch_used,
        best_validation_loss,
        threshold_payload["threshold"],
    )

    return {
        "epoch_used": epoch_used,
        "best_validation_loss": best_validation_loss,
        "model_saved": MODEL_PATH.exists(),
        "threshold_saved": THRESHOLD_PATH.exists(),
        "history_saved": TRAINING_HISTORY_PATH.exists(),
    }


def print_sprint_4_report(result: Dict[str, Any]) -> None:
    """Menampilkan laporan akhir Sprint 4."""
    print("=========================")
    print("SPRINT 4 REPORT")
    print("=========================")
    print("Dataset Loaded : OK")
    print("Training : OK")
    print(f"Epoch Used : {result['epoch_used']}")
    print(f"Best Validation Loss : {result['best_validation_loss']}")
    print(f"Model Saved : {'OK' if result['model_saved'] else 'FAILED'}")
    print(f"Threshold Saved : {'OK' if result['threshold_saved'] else 'FAILED'}")
    print(f"History Saved : {'OK' if result['history_saved'] else 'FAILED'}")
    print("Sprint 4 Status : COMPLETE")


if __name__ == "__main__":
    training_result = run_training()
    print_sprint_4_report(training_result)
