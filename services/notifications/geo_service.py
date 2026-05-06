"""Geospatial utilities — Haversine formula for 5km radius calculation."""
import math
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from shared.dynamodb import get_table, handle_client_error
from shared.logging_config import get_logger
from services.notifications.models import GeoPoint, NearbyUser

logger = get_logger(__name__)

EARTH_RADIUS_KM = 6371.0
DEFAULT_RADIUS_KM = float(os.getenv("NOTIFICATION_RADIUS_KM", "5.0"))
USERS_TABLE = os.getenv("USERS_TABLE", "fire_users")


def haversine_distance(point_a: GeoPoint, point_b: GeoPoint) -> float:
    """
    Calculate the great-circle distance between two geo points using
    the Haversine formula.

    Returns:
        Distance in kilometers (float).
    """
    lat1, lon1 = math.radians(point_a.latitude), math.radians(point_a.longitude)
    lat2, lon2 = math.radians(point_b.latitude), math.radians(point_b.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return round(EARTH_RADIUS_KM * c, 4)


async def get_users_within_radius(
    epicenter: GeoPoint,
    radius_km: float = DEFAULT_RADIUS_KM,
) -> list[NearbyUser]:
    """
    Scan the users table and filter those within `radius_km` of the epicenter.

    NOTE: For production scale, replace the full Scan with a geohash-based
    GSI query (e.g., S2 library or geohash tiles) to avoid full table scans.
    """
    table = get_table(USERS_TABLE)

    try:
        response = table.scan(
            ProjectionExpression="user_id, email, phone_number, #lat, #lon",
            ExpressionAttributeNames={"#lat": "latitude", "#lon": "longitude"},
        )
        items: list[dict[str, Any]] = response.get("Items", [])

        # Handle DynamoDB pagination
        while "LastEvaluatedKey" in response:
            response = table.scan(
                ProjectionExpression="user_id, email, phone_number, #lat, #lon",
                ExpressionAttributeNames={"#lat": "latitude", "#lon": "longitude"},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
    except ClientError as exc:
        handle_client_error(exc, "get_users_within_radius")

    nearby: list[NearbyUser] = []
    for item in items:
        try:
            user_location = GeoPoint(
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
            )
            distance = haversine_distance(epicenter, user_location)
            if distance <= radius_km:
                nearby.append(
                    NearbyUser(
                        user_id=item["user_id"],
                        email=item["email"],
                        phone_number=item.get("phone_number"),
                        distance_km=distance,
                    )
                )
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("skip_user_geo_data", user_id=item.get("user_id"), error=str(exc))

    logger.info(
        "users_in_radius",
        epicenter_lat=epicenter.latitude,
        epicenter_lon=epicenter.longitude,
        radius_km=radius_km,
        users_found=len(nearby),
    )
    return nearby
