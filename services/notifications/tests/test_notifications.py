"""Tests for the Notifications microservice."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.notifications.geo_service import haversine_distance
from services.notifications.handler import _deserialize_dynamodb_item, _extract_alert, handler
from services.notifications.models import FireAlert, GeoPoint, NearbyUser


# ── Haversine distance tests ───────────────────────────────────────────────────

class TestHaversineDistance:
    def test_same_point_is_zero(self):
        point = GeoPoint(latitude=40.7128, longitude=-74.0060)
        assert haversine_distance(point, point) == 0.0

    def test_known_distance_new_york_to_newark(self):
        new_york = GeoPoint(latitude=40.7128, longitude=-74.0060)
        newark = GeoPoint(latitude=40.7357, longitude=-74.1724)
        distance = haversine_distance(new_york, newark)
        # New York to Newark is ~14.7 km
        assert 14.0 < distance < 16.0

    def test_under_5km(self):
        origin = GeoPoint(latitude=40.7128, longitude=-74.0060)
        nearby = GeoPoint(latitude=40.7200, longitude=-74.0100)  # ~0.85 km away
        assert haversine_distance(origin, nearby) < 5.0

    def test_over_5km(self):
        origin = GeoPoint(latitude=40.7128, longitude=-74.0060)
        far = GeoPoint(latitude=40.7600, longitude=-74.1000)  # ~10+ km away
        assert haversine_distance(origin, far) > 5.0

    def test_returns_float(self):
        a = GeoPoint(latitude=0.0, longitude=0.0)
        b = GeoPoint(latitude=1.0, longitude=1.0)
        result = haversine_distance(a, b)
        assert isinstance(result, float)


# ── DynamoDB deserializer tests ────────────────────────────────────────────────

class TestDynamoDBDeserializer:
    def test_deserialize_string(self):
        raw = {"report_id": {"S": "rpt-001"}, "severity": {"S": "high"}}
        result = _deserialize_dynamodb_item(raw)
        assert result["report_id"] == "rpt-001"
        assert result["severity"] == "high"

    def test_deserialize_number(self):
        raw = {"confidence": {"N": "95.5"}}
        result = _deserialize_dynamodb_item(raw)
        assert result["confidence"] == 95.5

    def test_deserialize_boolean(self):
        raw = {"confirmed": {"BOOL": True}}
        result = _deserialize_dynamodb_item(raw)
        assert result["confirmed"] is True


# ── Alert extraction tests ─────────────────────────────────────────────────────

class TestExtractAlert:
    def _base_image(self) -> dict:
        return {
            "report_id": "rpt-abc",
            "title": "Fire in sector 7",
            "severity": "high",
            "status": "fire_confirmed",
            "location": json.dumps({"latitude": 40.7128, "longitude": -74.0060}),
            "reporter_id": "user-123",
            "validated_at": "2026-05-06T12:00:00+00:00",
        }

    def test_extracts_valid_alert(self):
        alert = _extract_alert(self._base_image())
        assert alert is not None
        assert alert.report_id == "rpt-abc"
        assert alert.severity == "high"
        assert alert.location.latitude == 40.7128

    def test_skips_non_confirmed_status(self):
        image = {**self._base_image(), "status": "pending"}
        assert _extract_alert(image) is None

    def test_skips_rejected_status(self):
        image = {**self._base_image(), "status": "rejected"}
        assert _extract_alert(image) is None

    def test_returns_none_on_missing_location(self):
        image = {**self._base_image()}
        del image["location"]
        result = _extract_alert(image)
        assert result is None

    def test_returns_none_on_invalid_location_json(self):
        image = {**self._base_image(), "location": "not-json"}
        result = _extract_alert(image)
        assert result is None


# ── Lambda handler integration tests ──────────────────────────────────────────

def _make_stream_event(status: str = "fire_confirmed") -> dict:
    """Build a mock DynamoDB Stream event."""
    return {
        "Records": [
            {
                "eventName": "INSERT",
                "dynamodb": {
                    "NewImage": {
                        "report_id": {"S": "rpt-stream-001"},
                        "title": {"S": "Wildfire north sector"},
                        "severity": {"S": "critical"},
                        "status": {"S": status},
                        "location": {
                            "S": json.dumps({"latitude": 40.7128, "longitude": -74.0060})
                        },
                        "reporter_id": {"S": "user-456"},
                        "validated_at": {"S": "2026-05-06T12:00:00+00:00"},
                    }
                },
            }
        ]
    }


@patch("services.notifications.handler.send_ses_email", new_callable=AsyncMock)
@patch("services.notifications.handler.publish_sns_alert", new_callable=AsyncMock)
@patch("services.notifications.handler.get_users_within_radius", new_callable=AsyncMock)
def test_handler_fire_confirmed_notifies_users(mock_geo, mock_sns, mock_ses):
    mock_geo.return_value = [
        NearbyUser(user_id="u1", email="alice@example.com", distance_km=2.3),
        NearbyUser(user_id="u2", email="bob@example.com", distance_km=4.1),
    ]
    mock_sns.return_value = ["sns-msg-001"]
    mock_ses.return_value = "ses-msg-001"

    result = handler(_make_stream_event("fire_confirmed"), context=None)

    assert result["statusCode"] == 200
    assert result["processed"] == 1
    assert result["skipped"] == 0
    mock_sns.assert_called_once()
    assert mock_ses.call_count == 2


@patch("services.notifications.handler.get_users_within_radius", new_callable=AsyncMock)
def test_handler_skips_non_confirmed(mock_geo):
    result = handler(_make_stream_event("pending"), context=None)
    assert result["skipped"] == 1
    assert result["processed"] == 0
    mock_geo.assert_not_called()


def test_handler_skip_modify_event():
    event = {
        "Records": [
            {
                "eventName": "MODIFY",
                "dynamodb": {"NewImage": {"status": {"S": "fire_confirmed"}}},
            }
        ]
    }
    result = handler(event, context=None)
    assert result["skipped"] == 1


def test_handler_empty_event():
    result = handler({"Records": []}, context=None)
    assert result["records_received"] == 0
    assert result["processed"] == 0


# ── Geo service tests ──────────────────────────────────────────────────────────

@patch("services.notifications.geo_service.get_table")
@pytest.mark.asyncio
async def test_get_users_within_radius(mock_get_table):
    mock_table = MagicMock()
    mock_table.scan.return_value = {
        "Items": [
            {
                "user_id": "u1",
                "email": "close@example.com",
                "latitude": "40.7200",
                "longitude": "-74.0100",  # ~0.85km from origin
            },
            {
                "user_id": "u2",
                "email": "far@example.com",
                "latitude": "41.0000",
                "longitude": "-74.0000",  # ~31km from origin
            },
        ]
    }
    mock_get_table.return_value = mock_table

    from services.notifications.geo_service import get_users_within_radius
    epicenter = GeoPoint(latitude=40.7128, longitude=-74.0060)
    result = await get_users_within_radius(epicenter, radius_km=5.0)

    assert len(result) == 1
    assert result[0].email == "close@example.com"
    assert result[0].distance_km < 5.0
