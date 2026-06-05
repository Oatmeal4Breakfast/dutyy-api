from datetime import datetime, UTC
from dataclasses import dataclass, field, asdict
from uuid import UUID, uuid7
from typing import Any

from src.domain.enums import DutyyStatus
from src.domain.exceptions import DomainValidationError
from src.domain.events import DutyyCompleted


@dataclass
class Dutyy:
    title: str
    project_id: UUID
    modified_date: datetime | None = None
    completed_date: datetime | None = None
    details: str | None = None
    events: list = field(default_factory=list, init=False, repr=False)
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: DutyyStatus = field(default=DutyyStatus.NEW)
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_title = self.title.strip().lower()

        if norm_title is None:
            raise DomainValidationError("Dutyy", ["title cannot be empty"])

        self.title = norm_title

        if isinstance(self.details, str):
            norm_details = self.details.strip()
            self.details = norm_details

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def _touch(self) -> None:
        self.modified_date = datetime.now(UTC)

    def update_title(self, new_title: str) -> None:
        normalized = new_title.strip().lower()
        if not normalized:
            raise DomainValidationError("Dutyy", ["title cannot be empty"])
        self.title: str = normalized
        self._touch()

    def update_project_id(self, new_project: UUID) -> None:
        if new_project == self.project_id:
            return
        self.project_id = new_project
        self._touch()

    def update_status(self, new_status: DutyyStatus) -> None:
        if new_status == self.status:
            return

        if new_status == DutyyStatus.COMPLETE:
            self.completed_date = datetime.now(UTC)
            self.events.append(
                DutyyCompleted(self.id, self.created_date, self.completed_date)
            )

        self.status = new_status
        self._touch()

    def update_details(self, details: str) -> None:
        normalized = details.strip()
        if normalized is None:
            return
        self.details = normalized
        self._touch()
