"""DynamoDB connection helper (boto3 direct, no ORM)."""
import os
from functools import lru_cache
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from shared.logging_config import get_logger

logger = get_logger(__name__)

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMODB_ENDPOINT_URL = os.getenv("DYNAMODB_ENDPOINT_URL")  # For local testing


@lru_cache(maxsize=1)
def get_dynamodb_resource() -> Any:
    """Return a cached DynamoDB resource."""
    kwargs: dict[str, Any] = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs)


def get_table(table_name: str) -> Any:
    """Return a DynamoDB Table object."""
    resource = get_dynamodb_resource()
    return resource.Table(table_name)


def handle_client_error(exc: ClientError, operation: str) -> None:
    """Log and re-raise DynamoDB ClientErrors with context."""
    code = exc.response["Error"]["Code"]
    message = exc.response["Error"]["Message"]
    logger.error(
        "dynamodb_client_error",
        operation=operation,
        error_code=code,
        error_message=message,
    )
    raise exc


__all__ = ["get_table", "handle_client_error", "Key", "Attr", "ClientError"]
