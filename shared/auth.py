"""JWT validation via AWS Cognito JWKS."""
import os
from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from shared.logging_config import get_logger

logger = get_logger(__name__)
bearer_scheme = HTTPBearer()

COGNITO_REGION = os.getenv("COGNITO_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID", "")

JWKS_URL = (
    f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/"
    f"{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
)


@lru_cache(maxsize=1)
def _get_jwks() -> dict[str, Any]:
    """Fetch and cache JWKS from Cognito."""
    response = httpx.get(JWKS_URL, timeout=10.0)
    response.raise_for_status()
    return response.json()


def _get_public_key(token: str) -> dict[str, Any]:
    """Extract the matching public key for a given token."""
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    jwks = _get_jwks()
    for key in jwks.get("keys", []):
        if key["kid"] == kid:
            return key
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Public key not found for token",
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a Cognito JWT."""
    try:
        public_key = _get_public_key(token)
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=COGNITO_CLIENT_ID,
        )
        return payload
    except JWTError as exc:
        logger.warning("jwt_validation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """FastAPI dependency that returns the authenticated user's claims."""
    return decode_token(credentials.credentials)


async def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """FastAPI dependency that requires the 'admin' Cognito group."""
    groups: list[str] = current_user.get("cognito:groups", [])
    if "admin" not in groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user
