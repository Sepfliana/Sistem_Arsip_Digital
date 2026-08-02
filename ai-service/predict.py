"""Prediksi anomali untuk satu audit log menggunakan model PyTorch VAE final."""

from __future__ import annotations

from typing import Any, Dict

from schemas.predict_request import PredictRequest
from services.inference import predict


def predict_audit_log(audit_log: Dict[str, Any]) -> Dict[str, Any]:
    """Menghasilkan status NORMAL atau ANOMALY untuk satu audit log."""
    request_payload = PredictRequest(**audit_log)
    return predict(request_payload)
