"""Compatibility entry point for the one active final VAE pipeline.

All preprocessing, model loading, thresholding, and explanations are owned by
``services.final_vae_pipeline``.  This module keeps existing imports stable
without retaining an alternate production path.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from services.final_vae_pipeline import (
    load_final_threshold,
    predict_final,
    reconstruction_details,
)


def reconstruction_errors(values: np.ndarray, batch_size: int = 4096) -> np.ndarray:
    """Return the unweighted mean of the nine squared feature errors."""
    return reconstruction_details(values, batch_size=batch_size)["anomaly_scores"]


def compute_training_threshold() -> float:
    """Compatibility name; final threshold is precomputed during final training."""
    return load_final_threshold()


def load_threshold() -> float:
    return load_final_threshold()


def ensure_training_threshold() -> float:
    """Verify, never fit or overwrite, the final threshold artifact."""
    return load_final_threshold()


def predict(payload: Any) -> dict[str, Any]:
    return predict_final(payload)
