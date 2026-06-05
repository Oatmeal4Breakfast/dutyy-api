from __future__ import annotations
from enum import StrEnum, auto
from dataclasses import dataclass, field
from datetime import datetime, UTC
from uuid import UUID, uuid7

from src.domain.dutyy import Dutyy


class ProjectStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()
    ABANDONED = auto()


@dataclass
class Project:
    name: str
    completed_date: datetime
    status: ProjectStatus = field(default=ProjectStatus.NEW)
    dutyys: list[Dutyy] = field(default_factory=list)
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: UUID = field(default_factory=uuid7)
