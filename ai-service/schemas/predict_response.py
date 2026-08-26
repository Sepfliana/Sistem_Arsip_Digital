"""Response contract for the final VAE inference endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DominantFeature(BaseModel):
    feature: str
    error: float
    contribution: float


class PredictResponse(BaseModel):
    anomaly_score: float
    reconstruction_error: float
    threshold: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    timestamp: str
    is_anomaly: bool
    status: Literal["NORMAL", "ANOMALY"]
    score: float
    feature_errors: dict[str, float] = Field(default_factory=dict)
    feature_contributions: dict[str, float] = Field(default_factory=dict)
    dominant_features: list[DominantFeature] = Field(default_factory=list)
    explanation: str = ""
    preprocessing_contract: str
