"""Tests for the Users microservice."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from services.users.main import app

client = TestClient(app)


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def valid_signup_payload() -> dict:
    return {
        "email": "john.doe@example.com",
        "password": "Str0ng!Pass",
        "full_name": "John Doe",
        "phone_number": "+15551234567",
    }


@pytest.fixture
def valid_login_payload() -> dict:
    return {"email": "john.doe@example.com", "password": "Str0ng!Pass"}


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "users"


# ── Sign Up ────────────────────────────────────────────────────────────────────

@patch("services.users.cognito_service.boto3.client")
def test_signup_success(mock_boto, valid_signup_payload):
    mock_cognito = MagicMock()
    mock_cognito.sign_up.return_value = {"UserSub": "abc-123-uuid"}
    mock_boto.return_value = mock_cognito

    response = client.post("/auth/signup", json=valid_signup_payload)
    assert response.status_code == 201
    data = response.json()
    assert data["user_sub"] == "abc-123-uuid"
    assert "message" in data


@pytest.mark.parametrize("bad_password", [
    "Sh1!",           # too short (under 8 chars minimum)
    "nouppercase1!",  # no uppercase letter
    "NOLOWERCASE1!",  # no lowercase letter
    "NoSpecialChar1", # no special character
    "NoDigitHere!A",  # no digit
])
def test_signup_weak_password(valid_signup_payload, bad_password):
    payload = {**valid_signup_payload, "password": bad_password}
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_signup_invalid_email(valid_signup_payload):
    payload = {**valid_signup_payload, "email": "not-an-email"}
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


def test_signup_invalid_phone(valid_signup_payload):
    payload = {**valid_signup_payload, "phone_number": "12345"}
    response = client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@patch("services.users.cognito_service.boto3.client")
def test_signup_duplicate_user(mock_boto, valid_signup_payload):
    from botocore.exceptions import ClientError
    mock_cognito = MagicMock()
    mock_cognito.sign_up.side_effect = ClientError(
        {"Error": {"Code": "UsernameExistsException", "Message": "Already exists"}},
        "SignUp",
    )
    mock_boto.return_value = mock_cognito

    response = client.post("/auth/signup", json=valid_signup_payload)
    assert response.status_code == 409


# ── Login ──────────────────────────────────────────────────────────────────────

@patch("services.users.cognito_service.boto3.client")
def test_login_success(mock_boto, valid_login_payload):
    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "access-token",
            "IdToken": "id-token",
            "RefreshToken": "refresh-token",
            "ExpiresIn": 3600,
        }
    }
    mock_boto.return_value = mock_cognito

    response = client.post("/auth/login", json=valid_login_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "access-token"
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 3600


@patch("services.users.cognito_service.boto3.client")
def test_login_invalid_credentials(mock_boto, valid_login_payload):
    from botocore.exceptions import ClientError
    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.side_effect = ClientError(
        {"Error": {"Code": "NotAuthorizedException", "Message": "Incorrect username or password"}},
        "InitiateAuth",
    )
    mock_boto.return_value = mock_cognito

    response = client.post("/auth/login", json=valid_login_payload)
    assert response.status_code == 401


# ── Refresh ────────────────────────────────────────────────────────────────────

@patch("services.users.cognito_service.boto3.client")
def test_refresh_token_success(mock_boto):
    mock_cognito = MagicMock()
    mock_cognito.initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "new-access-token",
            "IdToken": "new-id-token",
            "ExpiresIn": 3600,
        }
    }
    mock_boto.return_value = mock_cognito

    response = client.post("/auth/refresh", json={"refresh_token": "valid-refresh-token-value"})
    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "new-access-token"


def test_refresh_missing_token():
    response = client.post("/auth/refresh", json={})
    assert response.status_code == 422
