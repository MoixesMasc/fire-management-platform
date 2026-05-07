"""Modelos Pydantic compartidos entre microservicios."""
from typing import Optional

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class GeoPoint(BaseModel):
    """Punto geográfico con validación de rango."""
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
