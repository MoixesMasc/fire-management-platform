"""Incidents router."""
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from shared.auth import get_current_user
from services.incidents import dynamodb_service
from services.incidents.models import (
    CreateReportRequest,
    IncidentStatus,
    ListReportsResponse,
    ReportResponse,
    SeverityLevel,
)

router = APIRouter(prefix="/reports", tags=["Incidents"])


@router.post(
    "",
    response_model=ReportResponse,
    status_code=201,
    summary="Create a new fire incident report",
)
async def create_report(
    payload: CreateReportRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ReportResponse:
    reporter_id = current_user.get("sub", "unknown")
    return await dynamodb_service.create_report(payload, reporter_id=reporter_id)


@router.get(
    "",
    response_model=ListReportsResponse,
    summary="List fire incident reports with optional filters",
)
async def list_reports(
    severity: Optional[SeverityLevel] = Query(default=None),
    status: Optional[IncidentStatus] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    next_token: Optional[str] = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> ListReportsResponse:
    items, last_key = await dynamodb_service.list_reports(
        severity=severity.value if severity else None,
        status=status.value if status else None,
        limit=limit,
        next_token=next_token,
    )
    return ListReportsResponse(items=items, count=len(items), last_evaluated_key=last_key)
