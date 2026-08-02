"""Request contract for VAE inference."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    """Audit-log fields sent by backend service."""

    model_config = ConfigDict(extra="ignore")

    waktu: str = Field(..., description="Timestamp audit log dalam format ISO string atau string datetime")
    user_id: int = Field(..., description="ID user pengakses")
    aksi: str = Field(..., description="Aktivitas/aksi yang dilakukan")
    status: str = Field(..., description="Status hasil aktivitas")
    device: str = Field(..., description="Perangkat yang digunakan")
    ip_address: str = Field(..., description="Alamat IP pengakses")
    durasi_ms: float = Field(0.0, ge=0, description="Durasi aktivitas dalam milidetik")
    jumlah_objek: float = Field(1.0, ge=0, description="Jumlah objek yang diproses")
