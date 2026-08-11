from __future__ import annotations

from typing import Annotated
from datetime import timedelta, datetime
from enum import StrEnum
from uuid import UUID

from fastapi import Depends, APIRouter
from pydantic import BaseModel, ConfigDict

from src.domain.api import APIKeyStatus, APIKeySummary
from src.domain.user import User
from src.service.api_service import APIService
from src.api.deps import get_current_user, get_api_service


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
    user_id: UUID
    key_name: str
    ttl: APIKeyExpiry


class APIKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: APIKeyStatus
    created_at: datetime
    last_used: datetime | None
    expires_at: datetime | None


router = APIRouter(
    prefix="/dutyy/api/v1/api-keys",
    tags=["auth", "api-keys"],
    dependencies=[Depends(get_current_user)],
)

_APIService = Annotated[APIService, Depends(get_api_service)]


@router.post(path="", status_code=201)
async def issue_new_key(request: IssueKeyRequest, service: _APIService):
    raw_key: str = await service.issue_new_key(
        user_id=request.user_id,
        key_name=request.key_name,
        ttl=request.ttl.to_timedelta(),
    )
    return {"api-key": raw_key}


@router.get(path="", response_model=list[APIKeyResponse])
async def get_api_keys(
    current_user: Annotated[User, Depends(get_current_user)], service: _APIService
):
    keys: list[APIKeySummary] = await service.get_keys_by_user_id(
        user_id=current_user.id
    )
    return [APIKeyResponse.model_validate(key) for key in keys]
