from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_api_service, get_auth_context
from src.domain.api import APIKeyStatus, APIKeySummary
from src.service.api_service import APIService
from src.service.auth_service import AuthContext, CredentialMethod


class APIKeyExpiry(StrEnum):
    SEVEN_DAYS = "7d"
    THIRTY_DAYS = "30d"
    NINETY_DAYS = "90d"
    ONE_YEAR = "1y"

    def to_timedelta(self) -> timedelta:
        return {
            APIKeyExpiry.SEVEN_DAYS: timedelta(days=7),
            APIKeyExpiry.THIRTY_DAYS: timedelta(days=30),
            APIKeyExpiry.NINETY_DAYS: timedelta(days=90),
            APIKeyExpiry.ONE_YEAR: timedelta(days=365),
        }[self]


class IssueKeyRequest(BaseModel):
    key_name: str
    ttl: APIKeyExpiry


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: APIKeyStatus
    created_date: datetime
    last_used: datetime | None
    expires_at: datetime | None


router = APIRouter(
    prefix="/dutyy/api/v1/api-keys",
    tags=["auth", "api-keys"],
)

APIServiceDep = Annotated[APIService, Depends(get_api_service)]
AuthCTXDep = Annotated[AuthContext, Depends(get_auth_context)]


@router.post(path="", status_code=201)
async def issue_new_key(
    ctx: AuthCTXDep,
    request: IssueKeyRequest,
    service: APIServiceDep,
):
    if ctx.method != CredentialMethod.SESSION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session authentication required",
        )

    raw_key: str = await service.issue_new_key(
        user_id=ctx.user.id,
        key_name=request.key_name,
        ttl=request.ttl.to_timedelta(),
    )
    return {"api-key": raw_key}


@router.get(path="", response_model=list[APIKeyResponse])
async def get_api_keys(ctx: AuthCTXDep, service: APIServiceDep):
    if ctx.method != CredentialMethod.SESSION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session authentication required",
        )

    keys: list[APIKeySummary] = await service.get_keys_by_user_id(user_id=ctx.user.id)
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.delete(path="/{key_id}", status_code=204)
async def delete_key(
    ctx: AuthCTXDep,
    service: APIServiceDep,
    key_id: UUID,
):
    if ctx.method != CredentialMethod.SESSION:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="session authentication required",
        )

    await service.revoke(user_id=ctx.user.id, key_id=key_id)
