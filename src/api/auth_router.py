from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from src.api.deps import (
    get_api_service,
    get_auth_service,
    get_current_user,
    get_device_auth_service,
    get_web_session_config,
)
from src.config import WebSessionConfig
from src.domain.device_auth import KeyLifetime
from src.domain.user import User, UserSummary
from src.service.api_service import APIService
from src.service.auth_service import AuthService, BrowserLogin, SessionState
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


class LoginResponse(BaseModel):
    user_summary: UserSummary


class SessionStateResponse(BaseModel):
    user_summary: UserSummary
    idle_expires_at: datetime
    absolute_expires_at: datetime


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

session_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid session",
)

router = APIRouter(prefix="/dutyy/api/v1/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
DeviceAuthServiceDep = Annotated[DeviceAuthService, Depends(get_device_auth_service)]
APIServiceDep = Annotated[APIService, Depends(get_api_service)]
WebSessionConfigDep = Annotated[WebSessionConfig, Depends(get_web_session_config)]


@router.post(path="/set-password", status_code=204)
async def set_user_password(request: SetPasswordRequest, service: AuthServiceDep):
    await service.set_password(
        raw_token=request.raw_token, new_password=request.new_password
    )
    return Response(status_code=204)


@router.post(path="/login", status_code=200)
async def login(
    request: LoginRequest,
    service: AuthServiceDep,
    config: WebSessionConfigDep,
    response: Response,
):
    login: BrowserLogin | None = await service.login(
        user_email=request.email, password=request.password
    )
    if login is None:
        raise credentials_exception

    response.set_cookie(
        key=config.cookie_name,
        value=login.raw_token,
        path="/",
        secure=config.secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user_summary=login.user_summary)


@router.get(path="/session", response_model=SessionStateResponse)
async def get_user_session(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    config: WebSessionConfigDep,
):
    cookie: str | None = request.cookies.get(config.cookie_name)

    if cookie is None:
        raise session_exception
    session_state: SessionState | None = await service.get_session_user(cookie)

    if session_state is None:
        raise session_exception

    response.headers["Cache-Control"] = "no-store"
    return SessionStateResponse(
        user_summary=session_state.user_summary,
        idle_expires_at=session_state.idle_expires_at,
        absolute_expires_at=session_state.absolute_expires_at,
    )


@router.post(path="/request-password-reset", status_code=204)
async def request_password_reset(
    request: PasswordResetRequest, service: AuthServiceDep
):
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
    service: DeviceAuthServiceDep,
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
    service: DeviceAuthServiceDep,
    api_service: APIServiceDep,
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
    service: DeviceAuthServiceDep,
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
