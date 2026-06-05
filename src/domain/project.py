from dataclasses import dataclass, field, asdict
from typing import Any
from datetime import datetime, UTC
from uuid import UUID, uuid7

from src.domain.dutyy import Dutyy
from src.domain.enums import ProjectStatus
from src.domain.exceptions import DomainValidationError


@dataclass
class Project:
    name: str
    modified_date: datetime | None = None
    completed_date: datetime | None = None
    status: ProjectStatus = field(default=ProjectStatus.NEW)
    dutyys: list[Dutyy] = field(default_factory=list)
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_name = self.name.strip().lower()

        if norm_name is None:
            raise DomainValidationError("Project", ["name cannot be empty"])

        self.name = norm_name

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def update_name(self, new_name: str) -> None:
        norm_name = new_name.strip().lower()
        if norm_name is None:
            return
        self.name = norm_name
