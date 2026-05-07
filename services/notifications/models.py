"""Pydantic v2 models for the Notifications microservice."""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from shared.models import GeoPoint  # noqa: F401 — re-exportado para uso interno


class NotificationChannel(str, Enum):
    SNS = "sns"
    SES = "ses"
    BOTH = "both"


class FireAlert(BaseModel):
    report_id: str
    title: str
    severity: str
    location: GeoPoint
    reporter_id: str
    validated_at: str
    s3_image_uri: Optional[str] = None


class NearbyUser(BaseModel):
    user_id: str
    email: str
    phone_number: Optional[str] = None
    distance_km: float


class NotificationResult(BaseModel):
    alert: FireAlert
    users_notified: int
    sns_message_ids: list[str] = []
    ses_message_ids: list[str] = []
    radius_km: float
    errors: list[str] = []


class DynamoDBStreamRecord(BaseModel):
    """Represents a single DynamoDB Stream record."""
    event_name: str  # INSERT | MODIFY | REMOVE
    new_image: Optional[dict[str, Any]] = None
    old_image: Optional[dict[str, Any]] = None
    approximate_creation_date_time: Optional[float] = None
