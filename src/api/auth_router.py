from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from src.api.deps import (
    get_api_service,
    get_auth_service,
    get_current_user,
    get_device_auth_service,
)
from src.domain.device_auth import KeyLifetime
from src.domain.user import User
from src.service.api_service import APIService
from src.service.auth_service import AuthService
from src.service.device_auth_service import (
    DeviceAuthError,
    DeviceAuthService,
    DeviceCodeClientData,
    PollResult,
    PollStatus,
)

if TYPE_CHECKING:
    from src.domain.device_auth import DeviceCode


class SetPasswordRequest(BaseModel):
    raw_token: str
    new_password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class DeviceAuthStartRequest(BaseModel):
    key_name: str | None = None
    key_lifetime: KeyLifetime = KeyLifetime.THIRTY_DAYS


class DeviceAuthStartResponse(BaseModel):
    device_code: str
    user_code: str
    expires_in: int
    verification_uri: str
    interval: int


class DeviceAuthPollRequest(BaseModel):
    device_code: str


class DeviceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DeviceAuthApproveRequest(BaseModel):
    user_code: str


class DeviceAuthApproveResponse(BaseModel):
    detail: str


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password",
    headers={"WWW-Authenticate": "Bearer"},
)
router = APIRouter(prefix="/dutyy/api/v1/auth", tags=["auth"])

_AuthService = Annotated[AuthService, Depends(get_auth_service)]
_DeviceAuthService = Annotated[DeviceAuthService, Depends(get_device_auth_service)]
_APIService = Annotated[APIService, Depends(get_api_service)]


@router.post(path="/set-password", status_code=204)
async def set_user_password(request: SetPasswordRequest, service: _AuthService):
    await service.set_password(
        raw_token=request.raw_token, new_password=request.new_password
    )
    return Response(status_code=204)


@router.post(path="/login", response_model=TokenResponse)
async def login(request: LoginRequest, service: _AuthService):
    jwt: str | None = await service.login(
        user_email=request.email, password=request.password
    )
    if jwt is None:
        raise credentials_exception
    return TokenResponse(access_token=jwt, token_type="bearer")


@router.post(path="/request-password-reset", status_code=204)
async def request_password_reset(request: PasswordResetRequest, service: _AuthService):
    await service.handle_password_reset(user_email=request.email)
    return Response(status_code=204)


_POLL_ERROR: dict[PollStatus, str] = {
    PollStatus.PENDING: "authorization_pending",
    PollStatus.EXPIRED: "expired_token",
    PollStatus.INVALID: "invalid_grant",
}


@router.post(
    path="/device/code", status_code=200, response_model=DeviceAuthStartResponse
)
async def start_device_auth(
    service: _DeviceAuthService,
    request: DeviceAuthStartRequest | None = None,
):
    request = request or DeviceAuthStartRequest()
    data: DeviceCodeClientData = await service.start(
        key_name=request.key_name, key_lifetime=request.key_lifetime
    )
    return DeviceAuthStartResponse(
        device_code=data.raw_device_code,
        user_code=data.user_code,
        expires_in=int((data.expires_at - datetime.now(UTC)).total_seconds()),
        verification_uri=data.verification_uri,
        interval=data.interval,
    )


@router.post(path="/device/token", status_code=200, response_model=DeviceTokenResponse)
async def poll(
    request: DeviceAuthPollRequest,
    service: _DeviceAuthService,
    api_service: _APIService,
):
    result: PollResult = await service.poll(device_code=request.device_code)

    if result.status is not PollStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": _POLL_ERROR[result.status]},
        )

    raw_key: str = await api_service.issue_new_key(
        user_id=result.user_id,
        key_name=result.key_name,
        ttl=result.key_lifetime.ttl,
    )
    return DeviceTokenResponse(access_token=raw_key)


@router.post(
    path="/device/auth", status_code=200, response_model=DeviceAuthApproveResponse
)
async def approve_device(
    request: DeviceAuthApproveRequest,
    service: _DeviceAuthService,
    user: Annotated[User, Depends(get_current_user)],
):
    result: DeviceCode | DeviceAuthError = await service.approve(
        request.user_code, user_id=user.id
    )

    if isinstance(result, DeviceAuthError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "approval failed",
        )

    return DeviceAuthApproveResponse(detail="Device approved. Return to your terminal.")
