"""AWS Cognito interactions for user management."""
import hashlib
import hmac
import base64
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from shared.logging_config import get_logger

logger = get_logger(__name__)

COGNITO_REGION = os.getenv("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET", "")


def _get_client() -> Any:
    return boto3.client("cognito-idp", region_name=COGNITO_REGION)


def _compute_secret_hash(username: str) -> str:
    """Compute the SECRET_HASH required when a Cognito app client has a secret."""
    if not COGNITO_CLIENT_SECRET:
        return ""
    message = username + COGNITO_CLIENT_ID
    dig = hmac.new(
        COGNITO_CLIENT_SECRET.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


def _cognito_error_to_http(exc: ClientError) -> HTTPException:
    """Map Cognito error codes to appropriate HTTP exceptions."""
    code = exc.response["Error"]["Code"]
    message = exc.response["Error"]["Message"]
    mapping = {
        "UsernameExistsException": (status.HTTP_409_CONFLICT, message),
        "UserNotFoundException": (status.HTTP_404_NOT_FOUND, "User not found"),
        "NotAuthorizedException": (status.HTTP_401_UNAUTHORIZED, "Invalid credentials"),
        "UserNotConfirmedException": (status.HTTP_403_FORBIDDEN, "Account not confirmed"),
        "InvalidPasswordException": (status.HTTP_422_UNPROCESSABLE_ENTITY, message),
        "TooManyRequestsException": (status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests"),
        "ExpiredCodeException": (status.HTTP_400_BAD_REQUEST, "Token expired"),
    }
    http_status, detail = mapping.get(code, (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal error"))
    return HTTPException(status_code=http_status, detail=detail)


async def sign_up(
    email: str,
    password: str,
    full_name: str,
    phone_number: str | None,
) -> dict[str, Any]:
    """Register a new user in Cognito."""
    client = _get_client()
    kwargs: dict[str, Any] = {
        "ClientId": COGNITO_CLIENT_ID,
        "Username": email,
        "Password": password,
        "UserAttributes": [
            {"Name": "email", "Value": email},
            {"Name": "name", "Value": full_name},
        ],
    }
    if phone_number:
        kwargs["UserAttributes"].append({"Name": "phone_number", "Value": phone_number})
    if COGNITO_CLIENT_SECRET:
        kwargs["SecretHash"] = _compute_secret_hash(email)

    try:
        response = client.sign_up(**kwargs)
        logger.info("user_signed_up", email=email, user_sub=response["UserSub"])
        return {"user_sub": response["UserSub"]}
    except ClientError as exc:
        logger.warning("sign_up_failed", email=email, error=str(exc))
        raise _cognito_error_to_http(exc) from exc


async def login(email: str, password: str) -> dict[str, Any]:
    """Authenticate a user and return tokens."""
    client = _get_client()
    auth_params: dict[str, str] = {
        "USERNAME": email,
        "PASSWORD": password,
    }
    if COGNITO_CLIENT_SECRET:
        auth_params["SECRET_HASH"] = _compute_secret_hash(email)

    try:
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
            ClientId=COGNITO_CLIENT_ID,
        )
        auth_result = response["AuthenticationResult"]
        logger.info("user_logged_in", email=email)
        return {
            "access_token": auth_result["AccessToken"],
            "id_token": auth_result["IdToken"],
            "refresh_token": auth_result["RefreshToken"],
            "expires_in": auth_result["ExpiresIn"],
        }
    except ClientError as exc:
        logger.warning("login_failed", email=email, error=str(exc))
        raise _cognito_error_to_http(exc) from exc


async def refresh_token(refresh_token_value: str) -> dict[str, Any]:
    """Use a refresh token to obtain new access and ID tokens."""
    client = _get_client()
    auth_params: dict[str, str] = {"REFRESH_TOKEN": refresh_token_value}
    if COGNITO_CLIENT_SECRET:
        # For REFRESH_TOKEN_AUTH, username is not available; use a placeholder
        auth_params["SECRET_HASH"] = _compute_secret_hash(COGNITO_CLIENT_ID)

    try:
        response = client.initiate_auth(
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters=auth_params,
            ClientId=COGNITO_CLIENT_ID,
        )
        auth_result = response["AuthenticationResult"]
        logger.info("token_refreshed")
        return {
            "access_token": auth_result["AccessToken"],
            "id_token": auth_result["IdToken"],
            "expires_in": auth_result["ExpiresIn"],
        }
    except ClientError as exc:
        logger.warning("token_refresh_failed", error=str(exc))
        raise _cognito_error_to_http(exc) from exc
