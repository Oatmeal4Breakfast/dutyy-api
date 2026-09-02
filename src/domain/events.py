from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
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
class ProjectPublished(Event):
    project_id: UUID
    name: str
    published_date: datetime
    owner_id: UUID


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
class OwnershipTransferred(Event):
    project_id: UUID
    new_owner: UUID


@dataclass(frozen=True)
class UserCreated(Event):
    user_id: UUID
    email: str
    full_name: str
    created_date: datetime


@dataclass(frozen=True)
class UserPasswordReset(Event):
    user_id: UUID
    email: str
    full_name: str
    reqested_date: datetime


@dataclass(frozen=True)
class UserStatusChanged(Event):
    user_id: UUID
    email: str
    full_name: str
    new_status: UserStatus
    modified_date: datetime


@dataclass(frozen=True)
class PasswordHashCreated(Event):
    user_id: UUID
    user_email: str
    first_name: str
    plain_text_password: str


@dataclass(frozen=True)
class PasswordTokenCreated(Event):
    user_id: UUID
    user_email: str
    first_name: str
    raw_token: str


@dataclass(frozen=True)
class PasswordResetRequested(Event):
    user_id: UUID
    user_email: str
    first_name: str
    raw_token: str
