from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from uuid import UUID
    from datetime import datetime
    from src.domain.user import UserStatus


class Event:
    pass


@dataclass(frozen=True)
class DutyyCompleted(Event):
    id: UUID
    created_date: datetime
    completed_date: datetime


@dataclass(frozen=True)
class ProjectCompleted(Event):
    id: UUID
    created_date: datetime
    completed_date: datetime


@dataclass(frozen=True)
class DutyyAdded(Event):
    dutyy_id: UUID
    project_id: UUID
    modified_date: datetime


@dataclass(frozen=True)
class DutyyRemoved(Event):
    dutyy_id: UUID
    project_id: UUID
    modified_date: datetime


@dataclass(frozen=True)
class OwnershipTransferred:
    project_id: UUID
    new_owner: UUID


@dataclass(frozen=True)
class UserCreated:
    user_id: UUID
    email: str
    full_name: str
    created_date: datetime


@dataclass(frozen=True)
class UserPasswordReset:
    user_id: UUID
    email: str
    full_name: str
    reqested_date: datetime


@dataclass(frozen=True)
class UserStatusChanged:
    user_id: UUID
    email: str
    full_name: str
    new_status: UserStatus
    modified_date: datetime
