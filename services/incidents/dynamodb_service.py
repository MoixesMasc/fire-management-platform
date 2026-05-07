"""DynamoDB operations for the Incidents microservice."""
import json
import os
from typing import Any, Optional
from uuid import uuid4

from botocore.exceptions import ClientError

from shared.dynamodb import Attr, Key, get_table, handle_client_error
from shared.logging_config import get_logger
from shared.utils import now_iso
from services.incidents.models import (
    CreateReportRequest,
    GeoLocation,
    IncidentStatus,
    ReportResponse,
)

logger = get_logger(__name__)

REPORTS_TABLE = os.getenv("REPORTS_TABLE", "fire_reports")


def _item_to_response(item: dict[str, Any]) -> ReportResponse:
    return ReportResponse(
        report_id=item["report_id"],
        title=item["title"],
        description=item["description"],
        location=GeoLocation(**json.loads(item["location"])),
        severity=item["severity"],
        status=item["status"],
        reporter_id=item["reporter_id"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
        image_s3_key=item.get("image_s3_key"),
    )


async def create_report(
    payload: CreateReportRequest,
    reporter_id: str,
) -> ReportResponse:
    """Persist a new fire incident report."""
    table = get_table(REPORTS_TABLE)
    report_id = str(uuid4())
    now = now_iso()

    item: dict[str, Any] = {
        "report_id": report_id,
        "title": payload.title,
        "description": payload.description,
        "location": payload.location.model_dump_json(),
        "severity": payload.severity.value,
        "status": IncidentStatus.PENDING.value,
        "reporter_id": reporter_id,
        "created_at": now,
        "updated_at": now,
    }
    if payload.image_s3_key:
        item["image_s3_key"] = payload.image_s3_key

    try:
        table.put_item(
            Item=item,
            ConditionExpression=Attr("report_id").not_exists(),
        )
        logger.info("report_created", report_id=report_id, reporter_id=reporter_id)
        return _item_to_response(item)
    except ClientError as exc:
        handle_client_error(exc, "create_report")


async def list_reports(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    next_token: Optional[str] = None,
) -> tuple[list[ReportResponse], Optional[str]]:
    """List reports with optional filters and pagination."""
    table = get_table(REPORTS_TABLE)

    # Build filter expression
    filter_parts = []
    if severity:
        filter_parts.append(Attr("severity").eq(severity))
    if status:
        filter_parts.append(Attr("status").eq(status))

    scan_kwargs: dict[str, Any] = {"Limit": limit}
    if filter_parts:
        combined = filter_parts[0]
        for part in filter_parts[1:]:
            combined = combined & part
        scan_kwargs["FilterExpression"] = combined

    if next_token:
        scan_kwargs["ExclusiveStartKey"] = json.loads(next_token)

    try:
        response = table.scan(**scan_kwargs)
        items = [_item_to_response(i) for i in response.get("Items", [])]
        last_key: Optional[str] = None
        if lek := response.get("LastEvaluatedKey"):
            last_key = json.dumps(lek)
        logger.info("reports_listed", count=len(items))
        return items, last_key
    except ClientError as exc:
        handle_client_error(exc, "list_reports")
