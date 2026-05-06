"""
Notifications Lambda Handler — triggered by DynamoDB Streams.

Event flow:
  DynamoDB Streams (fire_validations table, INSERT with status=fire_confirmed)
  → This Lambda
  → Geo query for users within 5km
  → SNS broadcast + SES per-user email
"""
import asyncio
import json
import os
from typing import Any

from boto3.dynamodb.types import TypeDeserializer

from shared.logging_config import get_logger, setup_logging
from services.notifications.geo_service import get_users_within_radius
from services.notifications.models import FireAlert, GeoPoint, NotificationResult
from services.notifications.notification_service import publish_sns_alert, send_ses_email

setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

_deserializer = TypeDeserializer()
NOTIFICATION_RADIUS_KM = float(os.getenv("NOTIFICATION_RADIUS_KM", "5.0"))


def _deserialize_dynamodb_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert DynamoDB typed format ({"S": "value"}) to plain Python dict."""
    return {k: _deserializer.deserialize(v) for k, v in raw.items()}


def _extract_alert(new_image: dict[str, Any]) -> FireAlert | None:
    """
    Parse the DynamoDB new image into a FireAlert.
    Returns None if the record should be skipped.
    """
    if new_image.get("status") != "fire_confirmed":
        return None

    try:
        location_raw = new_image.get("location", "{}")
        if isinstance(location_raw, str):
            location_data = json.loads(location_raw)
        else:
            location_data = location_raw

        return FireAlert(
            report_id=new_image["report_id"],
            title=new_image.get("title", "Fire Incident"),
            severity=new_image.get("severity", "high"),
            location=GeoPoint(
                latitude=float(location_data["latitude"]),
                longitude=float(location_data["longitude"]),
            ),
            reporter_id=new_image.get("reporter_id", ""),
            validated_at=new_image.get("validated_at", new_image.get("updated_at", "")),
            s3_image_uri=new_image.get("s3_image_uri"),
        )
    except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("alert_parse_failed", error=str(exc))
        return None


async def _process_record(record: dict[str, Any]) -> NotificationResult | None:
    """Process a single DynamoDB Stream record."""
    event_name = record.get("eventName", "")

    # Only act on INSERT events for newly confirmed fire validations
    if event_name != "INSERT":
        logger.debug("skip_record", event_name=event_name)
        return None

    stream_record = record.get("dynamodb", {})
    raw_new_image = stream_record.get("NewImage")
    if not raw_new_image:
        return None

    new_image = _deserialize_dynamodb_item(raw_new_image)
    alert = _extract_alert(new_image)
    if alert is None:
        return None

    logger.info(
        "processing_fire_alert",
        report_id=alert.report_id,
        severity=alert.severity,
        lat=alert.location.latitude,
        lon=alert.location.longitude,
    )

    # Get users within radius
    nearby_users = await get_users_within_radius(alert.location, radius_km=NOTIFICATION_RADIUS_KM)

    # Broadcast to SNS topic (all subscribers)
    sns_message_ids = await publish_sns_alert(alert)

    # Send individual SES emails to nearby users
    ses_message_ids: list[str] = []
    errors: list[str] = []

    for user in nearby_users:
        message_id = await send_ses_email(alert, user)
        if message_id:
            ses_message_ids.append(message_id)
        else:
            errors.append(f"SES failed for {user.email}")

    result = NotificationResult(
        alert=alert,
        users_notified=len(nearby_users),
        sns_message_ids=sns_message_ids,
        ses_message_ids=ses_message_ids,
        radius_km=NOTIFICATION_RADIUS_KM,
        errors=errors,
    )

    logger.info(
        "notification_complete",
        report_id=alert.report_id,
        users_notified=result.users_notified,
        sns_count=len(sns_message_ids),
        ses_count=len(ses_message_ids),
        error_count=len(errors),
    )
    return result


async def _async_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Async core of the Lambda handler."""
    records = event.get("Records", [])
    logger.info("lambda_invoked", record_count=len(records))

    results = await asyncio.gather(
        *[_process_record(record) for record in records],
        return_exceptions=True,
    )

    processed = 0
    skipped = 0
    failed = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error("record_processing_error", error=str(result))
            failed += 1
        elif result is None:
            skipped += 1
        else:
            processed += 1

    summary = {
        "statusCode": 200,
        "records_received": len(records),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
    }
    logger.info("lambda_complete", **summary)
    return summary


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point."""
    return asyncio.get_event_loop().run_until_complete(_async_handler(event, context))
