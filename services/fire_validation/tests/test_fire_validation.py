"""Tests for the Fire Validation microservice."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.fire_validation.main import app
from services.fire_validation.models import RekognitionLabel, ValidationStatus
from shared import auth as auth_module


def _mock_user() -> dict:
    return {"sub": "user-123", "email": "validator@example.com"}


app.dependency_overrides[auth_module.get_current_user] = _mock_user
client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_validate_payload() -> dict:
    return {
        "s3_bucket": "fire-platform-images",
        "s3_key": "uploads/fire_scene_001.jpg",
        "report_id": "rpt-abc-123",
        "min_confidence": 80.0,
    }


MOCK_LABELS_WITH_FIRE = [
    RekognitionLabel(name="Fire", confidence=95.5, parents=["Nature"]),
    RekognitionLabel(name="Smoke", confidence=88.2, parents=["Nature"]),
    RekognitionLabel(name="Tree", confidence=72.0, parents=["Plant"]),
]


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "fire_validation"


# ── Validate — Fire Confirmed ──────────────────────────────────────────────────

@patch("services.fire_validation.router.dynamodb_service.save_validation_result")
@patch("services.fire_validation.router.rekognition_service.detect_fire_in_image")
async def test_validate_fire_confirmed(mock_detect, mock_save, valid_validate_payload):
    mock_detect.return_value = (
        ValidationStatus.FIRE_CONFIRMED,
        95.5,
        MOCK_LABELS_WITH_FIRE,
        ["Fire", "Smoke"],
    )
    from services.fire_validation.models import ValidateResponse
    mock_save.return_value = ValidateResponse(
        validation_id="val-001",
        report_id="rpt-abc-123",
        status=ValidationStatus.FIRE_CONFIRMED,
        confidence_score=95.5,
        labels_detected=MOCK_LABELS_WITH_FIRE,
        fire_labels=["Fire", "Smoke"],
        s3_image_uri="s3://fire-platform-images/uploads/fire_scene_001.jpg",
        validated_at="2026-05-06T12:00:00+00:00",
        message="Fire confirmed. Report validated and authorities notified.",
    )

    response = client.post(
        "/validate",
        json=valid_validate_payload,
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fire_confirmed"
    assert data["confidence_score"] == 95.5
    assert "Fire" in data["fire_labels"]


# ── Validate — No Fire ─────────────────────────────────────────────────────────

@patch("services.fire_validation.router.dynamodb_service.save_validation_result")
@patch("services.fire_validation.router.rekognition_service.detect_fire_in_image")
async def test_validate_no_fire(mock_detect, mock_save, valid_validate_payload):
    mock_detect.return_value = (ValidationStatus.FIRE_NOT_DETECTED, None, [], [])
    from services.fire_validation.models import ValidateResponse
    mock_save.return_value = ValidateResponse(
        validation_id="val-002",
        report_id="rpt-abc-123",
        status=ValidationStatus.FIRE_NOT_DETECTED,
        confidence_score=None,
        labels_detected=[],
        fire_labels=[],
        s3_image_uri="s3://fire-platform-images/uploads/fire_scene_001.jpg",
        validated_at="2026-05-06T12:00:00+00:00",
        message="No fire detected. Report marked as rejected.",
    )

    response = client.post(
        "/validate",
        json=valid_validate_payload,
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "fire_not_detected"


# ── Rekognition Unit Tests ─────────────────────────────────────────────────────

@patch("services.fire_validation.rekognition_service.boto3.client")
@pytest.mark.asyncio
async def test_detect_fire_labels(mock_boto):
    mock_client = MagicMock()
    mock_client.detect_labels.return_value = {
        "Labels": [
            {"Name": "Fire", "Confidence": 96.0, "Parents": [{"Name": "Nature"}]},
            {"Name": "Smoke", "Confidence": 84.5, "Parents": [{"Name": "Nature"}]},
            {"Name": "Forest", "Confidence": 78.0, "Parents": [{"Name": "Nature"}]},
        ]
    }
    mock_boto.return_value = mock_client

    from services.fire_validation.rekognition_service import detect_fire_in_image
    status, confidence, labels, fire_labels = await detect_fire_in_image(
        s3_bucket="test-bucket",
        s3_key="test.jpg",
        min_confidence=80.0,
    )

    assert status == ValidationStatus.FIRE_CONFIRMED
    assert confidence == 96.0
    assert "Fire" in fire_labels
    assert "Smoke" in fire_labels
    assert len(labels) == 3


@patch("services.fire_validation.rekognition_service.boto3.client")
@pytest.mark.asyncio
async def test_detect_no_fire_labels(mock_boto):
    mock_client = MagicMock()
    mock_client.detect_labels.return_value = {
        "Labels": [
            {"Name": "Mountain", "Confidence": 92.0, "Parents": []},
            {"Name": "Sky", "Confidence": 88.0, "Parents": []},
        ]
    }
    mock_boto.return_value = mock_client

    from services.fire_validation.rekognition_service import detect_fire_in_image
    status, confidence, labels, fire_labels = await detect_fire_in_image(
        s3_bucket="test-bucket",
        s3_key="landscape.jpg",
    )

    assert status == ValidationStatus.FIRE_NOT_DETECTED
    assert confidence is None
    assert fire_labels == []


# ── Validation Errors ──────────────────────────────────────────────────────────

def test_validate_missing_s3_key():
    response = client.post(
        "/validate",
        json={"s3_bucket": "bucket", "report_id": "rpt-123"},
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 422


def test_validate_invalid_confidence():
    response = client.post(
        "/validate",
        json={
            "s3_bucket": "bucket",
            "s3_key": "key.jpg",
            "report_id": "rpt-123",
            "min_confidence": 10.0,  # below 50.0 minimum
        },
        headers={"Authorization": "Bearer fake-token"},
    )
    assert response.status_code == 422
