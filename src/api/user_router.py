from __future__ import annotations
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from src.api.deps import get_user_service
from src.domain.user import UserStatus, UserUpdateFields, UserSummary
from src.service.user_service import UserService


class CreateUserRequest(BaseModel):
    first_name: str
    last_name: str
    email: str


class UserUpdateRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    status: UserStatus | None = None

    @property
    def is_empty(self) -> bool:
        return (
            self.first_name is None
            and self.last_name is None
            and self.email is None
            and self.status is None
        )


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


@router.get(path="/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID, service: UserService = Depends(get_user_service)
) -> UserResponse:
    user: UserSummary = await service.get_user_by_id(user_id)
    return UserResponse.model_validate(user)


@router.post(path="/users", response_model=UserResponse)
async def create_user(
    user: CreateUserRequest, service: UserService = Depends(get_user_service)
) -> UserResponse:
    new_user: UserSummary = await service.create_user(
        fname=user.first_name, lname=user.last_name, email=user.email
    )
    return UserResponse.model_validate(new_user)


@router.get(path="/users", response_model=list[UserResponse])
async def get_all_users(
    page: int = 1,
    page_size: int = 100,
    service: UserService = Depends(get_user_service),
) -> list[UserResponse]:
    users: list[UserSummary] = await service.get_all_users(
        page=page, page_size=page_size
    )
    return [UserResponse.model_validate(user) for user in users]


@router.patch(path="/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    if payload.is_empty:
        raise HTTPException(status_code=400, detail="no fields provided to update")

    updated: UserSummary = await service.update_user(
        user_id=user_id,
        changes=(
            UserUpdateFields(
                first_name=payload.first_name,
                last_name=payload.last_name,
                email=payload.email,
                status=payload.status,
            )
        ),
    )
    return UserResponse.model_validate(updated)
