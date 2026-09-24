from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from src.api.deps import (
    get_api_service,
    require_allowed_origin,
    require_csrf_token,
    require_session,
)
from src.domain.api import APIKeyStatus, APIKeySummary
from src.service.api_service import APIService
from src.service.auth_service import AuthContext


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
    id: UUID
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
SessionAuthDep = Annotated[AuthContext, Depends(require_session)]
OriginDep = Annotated[None, Depends(require_allowed_origin)]
CSRFDep = Annotated[None, Depends(require_csrf_token)]


@router.post(path="", status_code=201)
async def issue_new_key(
    session: SessionAuthDep,
    request: IssueKeyRequest,
    service: APIServiceDep,
    _: OriginDep,
    __: CSRFDep,
):

    raw_key: str = await service.issue_new_key(
        user_id=session.user.id,
        key_name=request.key_name,
        ttl=request.ttl.to_timedelta(),
    )
    return {"api-key": raw_key}


@router.get(path="", response_model=list[APIKeyResponse])
async def get_api_keys(
    session: SessionAuthDep,
    service: APIServiceDep,
):

    keys: list[APIKeySummary] = await service.get_keys_by_user_id(
        user_id=session.user.id
    )
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.delete(path="/{key_id}", status_code=204)
async def delete_key(
    session: SessionAuthDep,
    service: APIServiceDep,
    key_id: UUID,
    _: OriginDep,
    __: CSRFDep,
):
    await service.revoke(user_id=session.user.id, key_id=key_id)
