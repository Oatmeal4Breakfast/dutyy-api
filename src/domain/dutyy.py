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

        if not norm_title:
            raise DomainValidationError("Dutyy", ["title cannot be empty"])

        self.title = norm_title

        if isinstance(self.details, str):
            norm_details = self.details.strip()
            self.details = norm_details

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def _touch(self) -> None:
        self.modified_date = datetime.now(UTC)

    def _mark_complete(self) -> None:
        self.status = DutyyStatus.COMPLETE
        self._touch()
        self.completed_date = datetime.now(UTC)
        self.events.append(
            DutyyCompleted(
                id=self.id,
                created_date=self.created_date,
                completed_date=self.completed_date,
            )
        )

    def _mark_in_progress(self) -> None:
        self.status = DutyyStatus.IN_PROGRESS
        self._touch()

    def update_title(self, title: str) -> None:
        normalized = title.strip().lower()
        if not normalized:
            raise DomainValidationError("Dutyy", ["title cannot be empty"])
        self.title: str = normalized
        self._touch()

    def update_project_id(self, project: UUID) -> None:
        if project == self.project_id:
            return
        self.project_id = project
        self._touch()

    def update_status(self, status: DutyyStatus) -> None:
        if status == self.status:
            return

        match status:
            case DutyyStatus.IN_PROGRESS:
                self._mark_in_progress()
            case DutyyStatus.COMPLETE:
                self._mark_complete()
            case _:
                raise DomainValidationError(
                    "Dutyy", [f"{status} is not a valid transition"]
                )

    def update_details(self, details: str) -> None:
        normalized = details.strip()
        if not normalized:
            return
        self.details = normalized
        self._touch()
