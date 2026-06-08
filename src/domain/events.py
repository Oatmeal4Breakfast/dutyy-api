from __future__ import annotations
from typing import TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from uuid import UUID
    from datetime import datetime


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
