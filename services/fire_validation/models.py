"""Pydantic v2 models for the Fire Validation microservice."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    FIRE_CONFIRMED = "fire_confirmed"
    FIRE_NOT_DETECTED = "fire_not_detected"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"


class ValidateRequest(BaseModel):
    s3_bucket: str = Field(..., min_length=3, max_length=63, description="S3 bucket name")
    s3_key: str = Field(
        ...,
        min_length=1,
        max_length=1024,
        pattern=r"^[a-zA-Z0-9!_.*'()/\-]+$",
        description="S3 object key of the image to validate",
    )
    report_id: str = Field(..., description="Associated incident report ID")
    min_confidence: float = Field(
        default=80.0,
        ge=50.0,
        le=99.9,
        description="Minimum Rekognition confidence threshold (%)",
    )


class RekognitionLabel(BaseModel):
    name: str
    confidence: float
    parents: list[str] = []


class ValidateResponse(BaseModel):
    validation_id: str
    report_id: str
    status: ValidationStatus
    confidence_score: Optional[float] = None
    labels_detected: list[RekognitionLabel] = []
    fire_labels: list[str] = []
    s3_image_uri: str
    validated_at: str
    message: str


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None
