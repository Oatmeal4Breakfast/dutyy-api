from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import UUID, uuid7

from src.domain.dutyy import Dutyy
from src.domain.events import (
    DutyyAdded,
    DutyyRemoved,
    OwnershipTransferred,
    ProjectCompleted,
    ProjectPublished,
)
from src.domain.exceptions import (
    DomainValidationError,
    DutyyAssignedError,
    DutyyNotAssignedError,
)


class PublishingStatus(StrEnum):
    DRAFT = auto()
    PUBLISHED = auto()


class ProjectStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()
    ABANDONED = auto()


@dataclass
class Project:
    name: str
    owner_id: UUID
    modified_date: datetime | None = None
    completed_date: datetime | None = None
    published_date: datetime | None = None
    events: list = field(default_factory=list, init=False, repr=False)
    status: ProjectStatus = field(default=ProjectStatus.NEW)
    dutyys: list[Dutyy] = field(default_factory=list)
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    publishing_status: PublishingStatus = field(default=PublishingStatus.DRAFT)
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_name = self.name.strip().lower()

        if not norm_name:
            raise DomainValidationError("Project", ["name cannot be empty"])

        self.name = norm_name

    def _touch(self) -> datetime:
        self.modified_date = datetime.now(UTC)
        return self.modified_date

    def _mark_in_progress(self) -> None:
        self.status = ProjectStatus.IN_PROGRESS
        self._touch()

    def _mark_complete(self) -> None:
        self.status = ProjectStatus.COMPLETE
        self._touch()
        self.completed_date = datetime.now(UTC)
        self.events.append(
            ProjectCompleted(self.id, self.created_date, self.completed_date)
        )

    def _mark_abandoned(self) -> None:
        self.status = ProjectStatus.ABANDONED
        self._touch()

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = asdict(self)
        data.pop("events", None)
        return data

    def update_name(self, name: str) -> None:
        norm_name = name.strip().lower()
        if not norm_name:
            raise DomainValidationError("Project", ["name cannot be empty"])
        self.name = norm_name
        self._touch()

    def update_status(self, status: ProjectStatus) -> None:
        if status == self.status:
            return
        match status:
            case ProjectStatus.IN_PROGRESS:
                self._mark_in_progress()
            case ProjectStatus.ABANDONED:
                self._mark_abandoned()
            case ProjectStatus.COMPLETE:
                self._mark_complete()
            case _:
                raise DomainValidationError(
                    "Project", [f"{status} is not a valid transition"]
                )

    def publish(self) -> None:
        if self.publishing_status == PublishingStatus.PUBLISHED:
            return
        self.publishing_status = PublishingStatus.PUBLISHED
        self.published_date = self._touch()
        self.events.append(
            ProjectPublished(
                project_id=self.id,
                name=self.name,
                published_date=self.published_date,
                owner_id=self.owner_id,
            )
        )

    def unpublish(self) -> None:
        if self.publishing_status == PublishingStatus.DRAFT:
            return
        self.publishing_status = PublishingStatus.DRAFT
        self._touch()

    def add_dutyy(self, dutyy: Dutyy) -> None:
        for d in self.dutyys:
            if d.id == dutyy.id:
                raise DutyyAssignedError(id=dutyy.id)

        self.dutyys.append(dutyy)
        mod_date = self._touch()
        self.events.append(
            DutyyAdded(dutyy_id=dutyy.id, project_id=self.id, modified_date=mod_date)
        )

    def delete_dutyy(self, dutyy: Dutyy) -> None:
        for idx, d in enumerate(self.dutyys):
            if d.id == dutyy.id:
                del self.dutyys[idx]
                mod_date = self._touch()
                self.events.append(
                    DutyyRemoved(
                        dutyy_id=dutyy.id,
                        project_id=self.id,
                        modified_date=mod_date,
                    )
                )
                return
        raise DutyyNotAssignedError(dutyy.id)

    def transfer_ownership(self, owner_id: UUID) -> None:
        if self.owner_id == owner_id:
            return
        self.owner_id = owner_id
        self._touch()
        self.events.append(OwnershipTransferred(project_id=self.id, new_owner=owner_id))

    def __hash__(self):
        return hash(self.id)
