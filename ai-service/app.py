"""FastAPI production entry point for the one final VAE pipeline."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from schemas.predict_request import PredictRequest
from schemas.predict_response import PredictResponse
from services.inference import ensure_training_threshold, predict
from services.model_loader import load_model
from utils.final_preprocessing_contract import (
    FEATURE_COLUMNS,
    _normalize_activity,
    _normalize_status,
    _normalize_device,
)

logger = logging.getLogger("predict_debug")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

app = FastAPI(
    title="Sistem Arsip Digital AI Service",
    description="Final PyTorch VAE: Stage 1 SSOT + Stage 2 preprocessing contract.",
    version="2.0.0-final",
)


@app.on_event("startup")
def initialise_inference() -> None:
    """Fail fast when paired final artifacts are incomplete or inconsistent."""
    load_model()
    ensure_training_threshold()
    logger.info("AI service started. Preprocessing contract: stage2-final-v2-bounded-ip-zscore")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "server": "OK",
        "model": "FINAL_READY",
        "endpoint": "/predict",
        "preprocessing_contract": "stage2-final-v2-bounded-ip-zscore",
    }


class BatchPredictItem(BaseModel):
    audit_log_id: int = Field(..., description="ID of the audit_log record")
    waktu: str = Field(..., description="Timestamp audit log")
    user_id: int = Field(..., description="ID user pengakses")
    aksi: str = Field(..., description="Aktivitas/aksi yang dilakukan")
    status: str = Field(..., description="Status hasil aktivitas")
    device: str = Field(..., description="Perangkat yang digunakan")
    ip_address: str = Field(..., description="Alamat IP pengakses")
    durasi_ms: float = Field(0.0, ge=0, description="Durasi aktivitas dalam milidetik")
    jumlah_objek: float = Field(1.0, ge=0, description="Jumlah objek yang diproses")


class BatchPredictRequest(BaseModel):
    records: list[BatchPredictItem] = Field(..., description="List of audit log records to analyze")


class BatchPredictResult(BaseModel):
    audit_log_id: int
    status: str
    anomaly_score: float
    threshold: float
    risk_level: str
    is_anomaly: bool
    feature_errors: dict[str, float] = {}
    feature_contributions: dict[str, float] = {}
    dominant_features: list[dict[str, Any]] = []
    explanation: str = ""
    preprocessing_contract: str = ""
    error: str | None = None


class BatchPredictResponse(BaseModel):
    results: list[BatchPredictResult]
    processed: int
    errors: int


@app.post("/predict", response_model=PredictResponse)
def predict_audit_log(payload: PredictRequest) -> PredictResponse:
    """Raw audit log -> Stage 2 contract -> final VAE -> explanation."""
    raw_aksi = payload.aksi
    raw_status = payload.status
    raw_device = payload.device
    raw_user_id = payload.user_id
    raw_ip = payload.ip_address

    norm_activity = _normalize_activity(raw_aksi)
    norm_status = _normalize_status(raw_status)
    norm_device = _normalize_device(raw_device)

    logger.info(
        "PREDICT_DEBUG | raw: aksi=%s status=%s device=%s user_id=%s ip=%s | "
        "normalized: activity=%s status=%s device=%s",
        raw_aksi, raw_status, raw_device[:40] if raw_device else "N/A",
        raw_user_id, raw_ip, norm_activity, norm_status, norm_device,
    )

    try:
        result = predict(payload)
        score = result.get("anomaly_score", result.get("score", -1))
        threshold = result.get("threshold", -1)
        risk = result.get("risk_level", "?")
        logger.info(
            "PREDICT_DEBUG | score=%.6f threshold=%.6f risk=%s status=%s",
            score, threshold, risk, result.get("status", "?"),
        )
        return PredictResponse(**result)
    except (FileNotFoundError, TypeError, ValueError) as error:
        logger.error("PREDICT_DEBUG | ERROR 400: %s", error)
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.error("PREDICT_DEBUG | ERROR 500: %s", error)
        raise HTTPException(status_code=500, detail=f"Inference model gagal diproses: {error}") from error


@app.post("/predict-batch", response_model=BatchPredictResponse)
def predict_batch(payload: BatchPredictRequest) -> BatchPredictResponse:
    """Batch predict multiple audit log records through the final VAE pipeline."""
    results: list[BatchPredictResult] = []
    error_count = 0

    for item in payload.records:
        try:
            record_dict = {
                "waktu": item.waktu,
                "user_id": item.user_id,
                "aksi": item.aksi,
                "status": item.status,
                "device": item.device,
                "ip_address": item.ip_address,
                "durasi_ms": item.durasi_ms,
                "jumlah_objek": item.jumlah_objek,
            }
            result = predict(record_dict)
            score = float(result.get("anomaly_score", result.get("score", 0)))
            threshold_val = float(result.get("threshold", 0))
            results.append(BatchPredictResult(
                audit_log_id=item.audit_log_id,
                status=result.get("status", "NORMAL"),
                anomaly_score=score,
                threshold=threshold_val,
                risk_level=result.get("risk_level", "LOW"),
                is_anomaly=result.get("is_anomaly", False),
                feature_errors=result.get("feature_errors", {}),
                feature_contributions=result.get("feature_contributions", {}),
                dominant_features=result.get("dominant_features", []),
                explanation=result.get("explanation", ""),
                preprocessing_contract=result.get("preprocessing_contract", ""),
            ))
        except Exception as error:
            error_count += 1
            logger.error("BATCH_PREDICT | audit_log_id=%s ERROR: %s", item.audit_log_id, error)
            results.append(BatchPredictResult(
                audit_log_id=item.audit_log_id,
                status="ERROR",
                anomaly_score=0,
                threshold=0,
                risk_level="LOW",
                is_anomaly=False,
                error=str(error),
            ))

    logger.info(
        "BATCH_PREDICT | processed=%d errors=%d total=%d",
        len(payload.records) - error_count, error_count, len(payload.records),
    )
    return BatchPredictResponse(
        results=results,
        processed=len(payload.records) - error_count,
        errors=error_count,
    )
