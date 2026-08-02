from __future__ import annotations
from typing import Annotated

from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr

from src.api.deps import get_auth_service
from src.service.auth_service import AuthService
from src.logger import get_logger

logger = get_logger(__name__)


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


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid username or password",
    headers={"WWW-Authenticate": "Bearer"},
)
router = APIRouter(prefix="/dutyy/api/v1/auth", tags=["auth"])

_AuthService = Annotated[AuthService, Depends(get_auth_service)]


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
    # Always return 204 regardless of whether the email exists to avoid
    # leaking which addresses are registered (user enumeration).
    await service.handle_password_reset(user_email=request.email)
    return Response(status_code=204)
