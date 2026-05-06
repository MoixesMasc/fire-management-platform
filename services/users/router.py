"""Auth router for the Users microservice."""
from fastapi import APIRouter

from services.users import cognito_service
from services.users.models import (
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    SignUpRequest,
    SignUpResponse,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=SignUpResponse,
    status_code=201,
    summary="Register a new user",
)
async def signup(payload: SignUpRequest) -> SignUpResponse:
    result = await cognito_service.sign_up(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        phone_number=payload.phone_number,
    )
    return SignUpResponse(user_sub=result["user_sub"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT tokens",
)
async def login(payload: LoginRequest) -> TokenResponse:
    tokens = await cognito_service.login(
        email=payload.email,
        password=payload.password,
    )
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Refresh access token using refresh token",
)
async def refresh(payload: RefreshRequest) -> RefreshResponse:
    tokens = await cognito_service.refresh_token(payload.refresh_token)
    return RefreshResponse(**tokens)
