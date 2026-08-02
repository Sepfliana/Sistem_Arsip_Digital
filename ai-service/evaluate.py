"""Evaluasi VAE untuk bahan pengujian BAB IV."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import numpy as np
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_curve,
)
from tensorflow import keras

from config import MODEL_PATH, THRESHOLD_PATH, TRAINING_HISTORY_PATH
from predict import load_threshold
from train import load_dataset
from utils.vae import get_custom_objects


EVALUATION_METRICS_PATH = TRAINING_HISTORY_PATH.parent / "evaluation_metrics.json"


def load_model() -> keras.Model:
    """Memuat model VAE terlatih."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError("vae_model.keras belum tersedia. Jalankan training terlebih dahulu.")

    return keras.models.load_model(MODEL_PATH, custom_objects=get_custom_objects())


def build_evaluation_samples(values: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Membuat data uji normal dan anomali sintetis untuk evaluasi terukur.

    Dataset produksi audit log tidak selalu memiliki label anomali. Untuk kebutuhan
    pengujian skripsi, sampel normal memakai data hasil preprocessing, sedangkan
    sampel anomali dibuat dengan perturbasi besar pada beberapa feature numerik
    dan kategorikal agar distribusinya menjauh dari pola training.
    """
    normal_values = values.astype("float32")
    anomaly_values = normal_values.copy()

    if anomaly_values.size == 0:
        raise ValueError("Dataset evaluasi kosong.")

    anomaly_values[:, 1:5] = -1
    anomaly_values[:, 5] = anomaly_values[:, 5] + 8.0
    anomaly_values[:, 6] = anomaly_values[:, 6] + 8.0
    anomaly_values[:, 7] = anomaly_values[:, 7] + 8.0
    anomaly_values[:, 8] = 23 - anomaly_values[:, 8]
    anomaly_values[:, 9] = 6 - anomaly_values[:, 9]

    evaluation_values = np.vstack([normal_values, anomaly_values]).astype("float32")
    labels = np.concatenate([
        np.zeros(len(normal_values), dtype=int),
        np.ones(len(anomaly_values), dtype=int),
    ])

    return evaluation_values, labels


def calculate_scores(model: keras.Model, values: np.ndarray) -> np.ndarray:
    """Menghitung reconstruction error untuk setiap sampel."""
    reconstructed = model.predict(values, verbose=0)
    return np.mean(np.square(values - reconstructed), axis=1)


def finite_or_none(values: np.ndarray) -> list[float | None]:
    """Mengubah nilai ROC non-finite menjadi null agar JSON tetap standar."""
    return [float(value) if np.isfinite(value) else None for value in values]


def run_evaluation() -> Dict[str, Any]:
    """Menghasilkan metrik evaluasi VAE dan menyimpannya ke JSON."""
    _, values = load_dataset()
    threshold_metadata = load_threshold()
    threshold = float(threshold_metadata["threshold"])
    model = load_model()

    evaluation_values, labels = build_evaluation_samples(values)
    scores = calculate_scores(model, evaluation_values)
    predictions = (scores > threshold).astype(int)

    fpr, tpr, roc_thresholds = roc_curve(labels, scores)
    matrix = confusion_matrix(labels, predictions, labels=[0, 1])
    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_rows": int(len(labels)),
        "normal_rows": int(np.sum(labels == 0)),
        "anomaly_rows": int(np.sum(labels == 1)),
        "threshold": threshold,
        "confusion_matrix": {
            "labels": ["NORMAL", "ANOMALY"],
            "matrix": matrix.astype(int).tolist(),
        },
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1_score": float(f1_score(labels, predictions, zero_division=0)),
        "roc": {
            "false_positive_rate": fpr.astype(float).tolist(),
            "true_positive_rate": tpr.astype(float).tolist(),
            "thresholds": finite_or_none(roc_thresholds),
        },
        "auc": float(auc(fpr, tpr)),
    }

    EVALUATION_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVALUATION_METRICS_PATH.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=4)

    return metrics


if __name__ == "__main__":
    print(json.dumps(run_evaluation(), indent=4))
