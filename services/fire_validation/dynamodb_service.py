"""DynamoDB persistence for fire validation results."""
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from botocore.exceptions import ClientError

from shared.dynamodb import get_table, handle_client_error
from shared.logging_config import get_logger
from services.fire_validation.models import (
    RekognitionLabel,
    ValidateResponse,
    ValidationStatus,
)

logger = get_logger(__name__)

VALIDATIONS_TABLE = os.getenv("VALIDATIONS_TABLE", "fire_validations")
REPORTS_TABLE = os.getenv("REPORTS_TABLE", "fire_reports")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


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
    now = _now_iso()
    s3_uri = f"s3://{s3_bucket}/{s3_key}"

    # Map validation status to report status
    report_status_map = {
        ValidationStatus.FIRE_CONFIRMED: "validated",
        ValidationStatus.FIRE_NOT_DETECTED: "rejected",
        ValidationStatus.INCONCLUSIVE: "pending",
        ValidationStatus.ERROR: "pending",
    }
    new_report_status = report_status_map[validation_status]

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

    message_map = {
        ValidationStatus.FIRE_CONFIRMED: "Fire confirmed. Report validated and authorities notified.",
        ValidationStatus.FIRE_NOT_DETECTED: "No fire detected. Report marked as rejected.",
        ValidationStatus.INCONCLUSIVE: "Analysis inconclusive. Manual review required.",
        ValidationStatus.ERROR: "Validation error. Report remains pending.",
    }

    return ValidateResponse(
        validation_id=validation_id,
        report_id=report_id,
        status=validation_status,
        confidence_score=confidence_score,
        labels_detected=all_labels,
        fire_labels=fire_labels,
        s3_image_uri=s3_uri,
        validated_at=now,
        message=message_map[validation_status],
    )
