from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.deps import (
    get_auth_context,
    get_user_service,
    require_allowed_origin,
    require_csrf_token,
)
from src.domain.user import UserStatus, UserSummary, UserUpdateFields
from src.service.auth_service import AuthContext
from src.service.user_service import UserService


class CreateUserRequest(BaseModel):
    first_name: str
    last_name: str
    email: str


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None

    @property
    def is_empty(self) -> bool:
        return self.first_name is None and self.last_name is None and self.email is None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    first_name: str
    last_name: str
    email: str
    last_login: datetime | None
    modified_date: datetime | None
    created_date: datetime
    status: UserStatus
    id: UUID


router = APIRouter(prefix="/dutyy/api/v1", tags=["Users"])

UserServiceDep = Annotated[UserService, Depends(get_user_service)]
AuthCtxDep = Annotated[AuthContext, Depends(get_auth_context)]
OriginDep = Annotated[None, Depends(require_allowed_origin)]
CSRFDep = Annotated[None, Depends(require_csrf_token)]


@router.get(path="/users/me", response_model=UserResponse)
async def get_user_by_id(service: UserServiceDep, ctx: AuthCtxDep) -> UserResponse:
    user: UserSummary = await service.get_user_by_id(user_id=ctx.user.id)
    return UserResponse.model_validate(user)


@router.post(path="/users", response_model=UserResponse)
async def create_user(
    user: CreateUserRequest, service: UserServiceDep, _: OriginDep
) -> UserResponse:
    new_user: UserSummary = await service.create_user(
        fname=user.first_name, lname=user.last_name, email=user.email
    )
    return UserResponse.model_validate(new_user)


# @router.get(path="/users", response_model=list[UserResponse])
# async def get_all_users(
#     service: UserServiceDep,
#     ctx: AuthCtxDep,
#     page: int = 1,
#     page_size: int = 100,
# ) -> list[UserResponse]:
#     users: list[UserSummary] = await service.get_all_users(
#         page=page, page_size=page_size
#     )
#     return [UserResponse.model_validate(user) for user in users]


@router.patch(path="/users/me", response_model=UserResponse)
async def update_user(
    ctx: AuthCtxDep,
    payload: UserUpdateRequest,
    service: UserServiceDep,
    _: OriginDep,
    __: CSRFDep,
) -> UserResponse:

    if payload.is_empty:
        raise HTTPException(status_code=400, detail="no fields provided to update")

    updated: UserSummary = await service.update_user(
        user_id=ctx.user.id,
        changes=(
            UserUpdateFields(
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
            )
        ),
    )
    return UserResponse.model_validate(updated)
