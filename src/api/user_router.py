from __future__ import annotations
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.deps import get_user_service
from src.domain.user import User, UserStatus, UserUpdateFields
from src.service.user_service import UserService


class CreateUserRequest(BaseModel):
    first_name: str
    last_name: str
    email: str


class UserResponse(BaseModel):
    first_name: str
    last_name: str
    email: str
    last_login: datetime | None
    modified_date: datetime | None
    created_date: datetime
    status: UserStatus
    id: UUID


class UserCreatedResponse(BaseModel):
    id: UUID
    full_name: str
    email: str


class UserUpdatedResponse(BaseModel):
    id: UUID
    full_name: str
    email: str
    status: UserStatus
    modified: datetime | None


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


router = APIRouter(prefix="/dutyy/api/v1", tags=["Users"])


@router.get(path="/users/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: UUID, service: UserService = Depends(get_user_service)
) -> UserResponse:
    user = await service.get_user_by_id(user_id)
    return UserResponse(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        last_login=user.last_login,
        modified_date=user.modified_date,
        created_date=user.created_date,
        status=user.status,
        id=user.id,
    )


@router.post(path="/users", response_model=UserCreatedResponse)
async def create_user(
    user: CreateUserRequest, service: UserService = Depends(get_user_service)
) -> UserCreatedResponse:
    new_user: User = await service.create_user(
        fname=user.first_name, lname=user.last_name, email=user.email
    )
    return UserCreatedResponse(
        id=new_user.id, full_name=new_user.full_name, email=new_user.email
    )


@router.patch(path="/users/{user_id}", response_model=UserUpdatedResponse)
async def update_user(
    user_id: UUID,
    payload: UserUpdateRequest,
    service: UserService = Depends(get_user_service),
) -> UserUpdatedResponse:
    if payload.is_empty:
        raise HTTPException(status_code=400, detail="no fields provided to update")

    updated = await service.update_user(
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

    return UserUpdatedResponse(
        id=updated.id,
        full_name=updated.full_name,
        email=updated.email,
        status=updated.status,
        modified=updated.modified_date,
    )
