"""Tests for the Incidents microservice."""
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.incidents.main import app

# Bypass JWT auth for all tests
app.dependency_overrides = {}


def _mock_user() -> dict:
    return {"sub": "user-123", "email": "test@example.com", "cognito:groups": ["user"]}


# Inject auth bypass
from shared import auth as auth_module

app.dependency_overrides[auth_module.get_current_user] = _mock_user

client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_report_payload() -> dict:
    return {
        "title": "Large wildfire spotted near pine forest",
        "description": "Smoke visible from 2km away, flames spreading rapidly towards north.",
        "location": {"latitude": 40.7128, "longitude": -74.0060},
        "severity": "high",
        "image_s3_key": "uploads/fire_001.jpg",
    }


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "incidents"


# ── Create Report ──────────────────────────────────────────────────────────────

@patch("services.incidents.dynamodb_service.get_table")
def test_create_report_success(mock_get_table, valid_report_payload):
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}
    mock_get_table.return_value = mock_table

    response = client.post(
        "/reports",
        json=valid_report_payload,
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == valid_report_payload["title"]
    assert data["severity"] == "high"
    assert data["status"] == "pending"
    assert "report_id" in data
    assert "created_at" in data


def test_create_report_missing_title():
    payload = {
        "description": "Some description about the fire.",
        "location": {"latitude": 40.7128, "longitude": -74.0060},
        "severity": "medium",
    }
    response = client.post("/reports", json=payload, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 422


def test_create_report_invalid_severity(valid_report_payload):
    payload = {**valid_report_payload, "severity": "catastrophic"}
    response = client.post("/reports", json=payload, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 422


def test_create_report_invalid_location(valid_report_payload):
    payload = {**valid_report_payload, "location": {"latitude": 999.0, "longitude": -74.0060}}
    response = client.post("/reports", json=payload, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 422


@pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
@patch("services.incidents.dynamodb_service.get_table")
def test_create_report_all_severities(mock_get_table, severity, valid_report_payload):
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}
    mock_get_table.return_value = mock_table

    payload = {**valid_report_payload, "severity": severity}
    response = client.post("/reports", json=payload, headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 201
    assert response.json()["severity"] == severity


# ── List Reports ───────────────────────────────────────────────────────────────

@patch("services.incidents.dynamodb_service.get_table")
def test_list_reports_empty(mock_get_table):
    mock_table = MagicMock()
    mock_table.scan.return_value = {"Items": [], "Count": 0}
    mock_get_table.return_value = mock_table

    response = client.get("/reports", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["count"] == 0


@patch("services.incidents.dynamodb_service.get_table")
def test_list_reports_with_items(mock_get_table):
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [
            {
                "report_id": "rpt-001",
                "title": "Forest fire alpha",
                "description": "Large blaze in sector 7 spreading east towards residential areas.",
                "location": json.dumps({"latitude": 40.7, "longitude": -74.0, "altitude_meters": None}),
                "severity": "critical",
                "status": "pending",
                "reporter_id": "user-123",
                "created_at": "2026-05-06T12:00:00+00:00",
                "updated_at": "2026-05-06T12:00:00+00:00",
                "image_s3_key": "uploads/fire_alpha.jpg",
            }
        ],
        "Count": 1,
    }
    mock_get_table.return_value = mock_table

    response = client.get("/reports", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["items"][0]["report_id"] == "rpt-001"


@patch("services.incidents.dynamodb_service.get_table")
def test_list_reports_pagination(mock_get_table):
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [],
        "LastEvaluatedKey": {"report_id": {"S": "rpt-099"}},
    }
    mock_get_table.return_value = mock_table

    response = client.get("/reports?limit=5", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 200
    assert response.json()["last_evaluated_key"] is not None


def test_list_reports_invalid_limit():
    response = client.get("/reports?limit=0", headers={"Authorization": "Bearer fake-token"})
    assert response.status_code == 422
