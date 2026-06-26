from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime, UTC

if TYPE_CHECKING:
    from datetime import datetime
    from src.domain.user import UserStatus


@dataclass(frozen=True)
class Event:
    event_id: UUID = field(default_factory=uuid4, kw_only=True)
    time_stamp: datetime = field(
        default_factory=lambda: datetime.now(UTC), kw_only=True
    )


@dataclass(frozen=True)
class DutyyCompleted(Event):
    duty_id: UUID
    created_date: datetime
    completed_date: datetime


@dataclass(frozen=True)
class ProjectCompleted(Event):
    project_id: UUID
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
