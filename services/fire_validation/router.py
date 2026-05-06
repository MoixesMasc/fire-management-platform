"""Fire Validation router."""
from typing import Any

from fastapi import APIRouter, Depends

from shared.auth import get_current_user
from services.fire_validation import dynamodb_service, rekognition_service
from services.fire_validation.models import ValidateRequest, ValidateResponse

router = APIRouter(prefix="/validate", tags=["Fire Validation"])


@router.post(
    "",
    response_model=ValidateResponse,
    status_code=200,
    summary="Validate a fire report image using AWS Rekognition",
)
async def validate_image(
    payload: ValidateRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ValidateResponse:
    """
    Accepts an S3 image location, runs AWS Rekognition label detection,
    and persists the fire validation result to DynamoDB.
    """
    validation_status, confidence_score, all_labels, fire_labels = (
        await rekognition_service.detect_fire_in_image(
            s3_bucket=payload.s3_bucket,
            s3_key=payload.s3_key,
            min_confidence=payload.min_confidence,
        )
    )

    return await dynamodb_service.save_validation_result(
        report_id=payload.report_id,
        s3_bucket=payload.s3_bucket,
        s3_key=payload.s3_key,
        validation_status=validation_status,
        confidence_score=confidence_score,
        all_labels=all_labels,
        fire_labels=fire_labels,
    )
