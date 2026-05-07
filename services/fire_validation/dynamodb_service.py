"""DynamoDB persistence for fire validation results."""
import os
from typing import Any
from uuid import uuid4

from botocore.exceptions import ClientError

from shared.dynamodb import get_table, handle_client_error
from shared.logging_config import get_logger
from shared.utils import now_iso
from services.fire_validation.models import (
    RekognitionLabel,
    ValidateResponse,
    ValidationStatus,
)

logger = get_logger(__name__)

VALIDATIONS_TABLE = os.getenv("VALIDATIONS_TABLE", "fire_validations")
REPORTS_TABLE = os.getenv("REPORTS_TABLE", "fire_reports")


MESSAGE_MAP = {
    "fire_confirmed":    "Fire confirmed. Report validated and authorities notified.",
    "fire_not_detected": "No fire detected. Report marked as rejected.",
    "inconclusive":      "Analysis inconclusive. Manual review required.",
    "error":             "Validation error. Report remains pending.",
}

REPORT_STATUS_MAP = {
    "fire_confirmed":    "validated",
    "fire_not_detected": "rejected",
    "inconclusive":      "pending",
    "error":             "pending",
}


async def save_validation_result(
    report_id: str,
    s3_bucket: str,
    s3_key: str,
    validation_status: ValidationStatus,
    confidence_score: float | None,
    all_labels: list[RekognitionLabel],
    fire_labels: list[str],
) -> ValidateResponse:
    """Persist validation result and update the parent report status."""
    validation_id = str(uuid4())
    now = now_iso()
    s3_uri = f"s3://{s3_bucket}/{s3_key}"
    new_report_status = REPORT_STATUS_MAP[validation_status.value]

    validations_table = get_table(VALIDATIONS_TABLE)
    item: dict[str, Any] = {
        "validation_id": validation_id,
        "report_id": report_id,
        "status": validation_status.value,
        "s3_image_uri": s3_uri,
        "fire_labels": fire_labels,
        "labels_count": len(all_labels),
        "validated_at": now,
    }
    if confidence_score is not None:
        item["confidence_score"] = str(confidence_score)

    try:
        validations_table.put_item(Item=item)
    except ClientError as exc:
        handle_client_error(exc, "save_validation_result")

    # Update the parent report's status
    try:
        reports_table = get_table(REPORTS_TABLE)
        reports_table.update_item(
            Key={"report_id": report_id},
            UpdateExpression="SET #s = :s, updated_at = :u",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": new_report_status, ":u": now},
        )
    except ClientError as exc:
        logger.warning("report_status_update_failed", report_id=report_id, error=str(exc))

    logger.info(
        "validation_saved",
        validation_id=validation_id,
        report_id=report_id,
        status=validation_status.value,
    )

    return ValidateResponse(
        validation_id=validation_id,
        report_id=report_id,
        status=validation_status,
        confidence_score=confidence_score,
        labels_detected=all_labels,
        fire_labels=fire_labels,
        s3_image_uri=s3_uri,
        validated_at=now,
        message=MESSAGE_MAP[validation_status.value],
    )
