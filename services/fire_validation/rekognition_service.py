"""AWS Rekognition integration for fire detection in images."""
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from shared.logging_config import get_logger
from services.fire_validation.models import RekognitionLabel, ValidationStatus

logger = get_logger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Labels that Rekognition associates with fire/smoke
FIRE_RELATED_LABELS = frozenset({
    "Fire",
    "Flame",
    "Smoke",
    "Bonfire",
    "Campfire",
    "Wildfire",
    "Burning",
    "Conflagration",
})


def _get_client() -> Any:
    return boto3.client("rekognition", region_name=AWS_REGION)


async def detect_fire_in_image(
    s3_bucket: str,
    s3_key: str,
    min_confidence: float = 80.0,
) -> tuple[ValidationStatus, float | None, list[RekognitionLabel], list[str]]:
    """
    Call Rekognition detect_labels on an S3 image and determine fire presence.

    Returns:
        (status, max_fire_confidence, all_labels, matched_fire_labels)
    """
    client = _get_client()

    try:
        response = client.detect_labels(
            Image={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
            MaxLabels=50,
            MinConfidence=min_confidence,
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "InvalidS3ObjectException":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image not found at s3://{s3_bucket}/{s3_key}",
            ) from exc
        if code == "InvalidImageException":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The provided file is not a valid image",
            ) from exc
        logger.error("rekognition_error", bucket=s3_bucket, key=s3_key, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Rekognition service error",
        ) from exc

    raw_labels = response.get("Labels", [])
    all_labels: list[RekognitionLabel] = [
        RekognitionLabel(
            name=lbl["Name"],
            confidence=round(lbl["Confidence"], 2),
            parents=[p["Name"] for p in lbl.get("Parents", [])],
        )
        for lbl in raw_labels
    ]

    fire_labels: list[str] = []
    max_confidence: float | None = None

    for label in all_labels:
        if label.name in FIRE_RELATED_LABELS:
            fire_labels.append(label.name)
            if max_confidence is None or label.confidence > max_confidence:
                max_confidence = label.confidence

    if fire_labels:
        validation_status = ValidationStatus.FIRE_CONFIRMED
    elif len(raw_labels) > 0:
        validation_status = ValidationStatus.FIRE_NOT_DETECTED
    else:
        validation_status = ValidationStatus.INCONCLUSIVE

    logger.info(
        "rekognition_completed",
        bucket=s3_bucket,
        key=s3_key,
        status=validation_status,
        fire_labels=fire_labels,
        max_confidence=max_confidence,
    )
    return validation_status, max_confidence, all_labels, fire_labels
