from dataclasses import field
from datetime import UTC, datetime
from enum import StrEnum, auto
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base
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


class Project(Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    owner_id: Mapped[UUID] = mapped_column(nullable=False)
    modified_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    published_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    events: list = field(default_factory=list, init=False, repr=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="projectstatus"),
        nullable=False,
        default=ProjectStatus.NEW,
    )
    dutyys: Mapped[list[Dutyy]] = relationship(
        default_factory=list,
        lazy="raise",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default_factory=lambda: datetime.now(UTC),
    )
    publishing_status: Mapped[PublishingStatus] = mapped_column(
        Enum(PublishingStatus, name="publishingstatus"),
        nullable=False,
        default=PublishingStatus.DRAFT,
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_name = self.name.strip().lower()

        if not norm_name:
            raise DomainValidationError("Project", ["name cannot be empty"])

        self.name = norm_name

    def _touch(self) -> datetime:
        self.modified_date: datetime = datetime.now(UTC)
        return self.modified_date

    def _mark_in_progress(self) -> None:
        self.status = ProjectStatus.IN_PROGRESS
        self._touch()

    def _mark_complete(self) -> None:
        self.status = ProjectStatus.COMPLETE
        self._touch()
        self.completed_date: datetime = datetime.now(UTC)
        self.events.append(
            ProjectCompleted(self.id, self.created_date, self.completed_date)
        )

    def _mark_abandoned(self) -> None:
        self.status = ProjectStatus.ABANDONED
        self._touch()

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
                if self.status == ProjectStatus.COMPLETE:
                    self.completed_date = None
                self._mark_in_progress()
            case ProjectStatus.ABANDONED:
                if self.status == ProjectStatus.COMPLETE:
                    self.completed_date = None
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

        if len(self.dutyys) <= 0:
            raise DomainValidationError("Project", ["project_has_no_dutyys"])
        self.publishing_status = PublishingStatus.PUBLISHED
        self.published_date: datetime = self._touch()
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
        if self.publishing_status != PublishingStatus.DRAFT:
            raise DomainValidationError("Project", ["project_not_in_draft_mode"])
        for d in self.dutyys:
            if d.id == dutyy.id:
                raise DutyyAssignedError(id=dutyy.id)

        self.dutyys.append(dutyy)
        mod_date = self._touch()
        self.events.append(
            DutyyAdded(dutyy_id=dutyy.id, project_id=self.id, modified_date=mod_date)
        )

    def delete_dutyy(self, dutyy_id: UUID) -> None:
        for idx, d in enumerate(self.dutyys):
            if d.id == dutyy_id:
                del self.dutyys[idx]
                mod_date = self._touch()
                self.events.append(
                    DutyyRemoved(
                        dutyy_id=dutyy_id,
                        project_id=self.id,
                        modified_date=mod_date,
                    )
                )
                return
        raise DutyyNotAssignedError(dutyy_id)

    def transfer_ownership(self, owner_id: UUID) -> None:
        if self.owner_id == owner_id:
            return
        self.owner_id = owner_id
        self._touch()
        self.events.append(OwnershipTransferred(project_id=self.id, new_owner=owner_id))

    def __hash__(self):
        return hash(self.id)
