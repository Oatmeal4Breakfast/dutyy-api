from __future__ import annotations
from datetime import datetime, UTC
from enum import StrEnum, auto
from dataclasses import dataclass, field
from uuid import UUID, uuid7


class DutyyStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()


@dataclass
class Dutyy:
    title: str
    details: str
    project_id: str
    modified_date: datetime
    completed_date: datetime
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: DutyyStatus = field(default=DutyyStatus.NEW)
    id: UUID = field(default_factory=uuid7)
