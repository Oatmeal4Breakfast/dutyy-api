from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


class Event:
    pass


@dataclass(frozen=True)
class UserCreated(Event):
    user_id: UUID
    email: str
    name: str
    created_date: datetime


@dataclass(frozen=True)
class UserPasswordReset(Event):
    user_id: UUID
    request_date: datetime


@dataclass(frozen=True)
class ProjectAssigned(Event):
    user_id: UUID
    project_id: UUID
    assigned_date: datetime
