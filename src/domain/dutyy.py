from dataclasses import field
from datetime import UTC, datetime
from enum import StrEnum, auto
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.domain.events import DutyyCompleted
from src.domain.exceptions import DomainValidationError


class DutyyStatus(StrEnum):
    NEW = auto()
    IN_PROGRESS = auto()
    COMPLETE = auto()


class Dutyy(Base):
    __tablename__ = "dutyys"

    title: Mapped[str] = mapped_column(String, nullable=False)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    modified_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    completed_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    events: list = field(default_factory=list, init=False, repr=False)
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default_factory=lambda: datetime.now(UTC),
    )
    status: Mapped[DutyyStatus] = mapped_column(
        Enum(DutyyStatus, name="dutyystatus"),
        nullable=False,
        default=DutyyStatus.NEW,
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_title = self.title.strip().lower()

        if not norm_title:
            raise DomainValidationError("Dutyy", ["title cannot be empty"])

        self.title = norm_title

        if isinstance(self.details, str):
            norm_details = self.details.strip()
            self.details = norm_details

    def _touch(self) -> None:
        self.modified_date = datetime.now(UTC)

    def _mark_complete(self) -> None:
        self.status = DutyyStatus.COMPLETE
        self._touch()
        self.completed_date = datetime.now(UTC)
        self.events.append(
            DutyyCompleted(
                duty_id=self.id,
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
                if self.status == DutyyStatus.COMPLETE:
                    self.completed_date = None
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

    def __hash__(self):
        return hash(self.id)
