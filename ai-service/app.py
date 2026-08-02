"""FastAPI service for inference with the final audit-log VAE."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException

from schemas.predict_request import PredictRequest
from schemas.predict_response import PredictResponse
from services.inference import ensure_training_threshold, predict


app = FastAPI(
    title="Sistem Arsip Digital AI Service",
    description="Deteksi anomali audit log menggunakan model PyTorch VAE final.",
    version="1.0.0",
)


@app.on_event("startup")
def initialise_inference() -> None:
    """Create the deployment threshold once when it does not yet exist."""
    ensure_training_threshold()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"server": "OK", "model": "READY"}


@app.post("/predict", response_model=PredictResponse)
def predict_audit_log(payload: PredictRequest) -> PredictResponse:
    """Score one audit-log event against the final VAE contract."""
    try:
        result = predict(payload)
        return PredictResponse(**result)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Inference model gagal diproses: {error}") from error
