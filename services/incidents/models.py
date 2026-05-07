"""Pydantic v2 models for the Incidents microservice."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from shared.models import GeoPoint


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"
    RESOLVED = "resolved"


class GeoLocation(GeoPoint):
    """Extiende GeoPoint con altitud opcional."""
    altitude_meters: Optional[float] = Field(default=None, ge=0.0)


class CreateReportRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    location: GeoLocation
    severity: SeverityLevel
    image_s3_key: Optional[str] = Field(
        default=None,
        description="S3 key of the uploaded image for validation",
        pattern=r"^[a-zA-Z0-9!_.*'()/\-]+$",
    )
    reporter_id: Optional[str] = Field(default=None, description="Filled from JWT claims")


class ReportResponse(BaseModel):
    report_id: str
    title: str
    description: str
    location: GeoLocation
    severity: SeverityLevel
    status: IncidentStatus
    reporter_id: str
    created_at: str
    updated_at: str
    image_s3_key: Optional[str] = None


class ListReportsResponse(BaseModel):
    items: list[ReportResponse]
    count: int
    last_evaluated_key: Optional[str] = Field(
        default=None,
        description="Pagination cursor — pass as `next_token` in the next request",
    )


class ListReportsQuery(BaseModel):
    severity: Optional[SeverityLevel] = None
    status: Optional[IncidentStatus] = None
    limit: int = Field(default=20, ge=1, le=100)
    next_token: Optional[str] = None
