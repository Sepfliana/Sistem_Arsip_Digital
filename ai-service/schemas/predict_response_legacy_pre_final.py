"""Response contract for VAE inference."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel


class PredictResponse(BaseModel):
    anomaly_score: float
    reconstruction_error: float
    threshold: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    timestamp: str
    is_anomaly: bool
    status: Literal["NORMAL", "ANOMALY"]
    score: float
