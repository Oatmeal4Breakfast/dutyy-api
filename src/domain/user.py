from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from uuid import UUID, uuid7

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import DateTime, Enum, String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.domain.events import UserCreated, UserPasswordReset, UserStatusChanged
from src.domain.exceptions import DomainValidationError


class UserStatus(StrEnum):
    ACTIVE = auto()
    INACTIVE = auto()
    BLOCKED = auto()


@dataclass(frozen=True)
class UserUpdateFields:
    first_name: str | None = None
    last_name: str | None = None
    status: UserStatus | None = None


@dataclass(frozen=True)
class UserSummary:
    first_name: str
    last_name: str
    email: str
    last_login: datetime | None
    modified_date: datetime | None
    created_date: datetime
    status: UserStatus
    id: UUID


class User(Base):
    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    modified_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default_factory=lambda: datetime.now(UTC),
    )
    events: list = field(default_factory=list, init=False, repr=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="userstatus"), nullable=False, default=UserStatus.ACTIVE
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @classmethod
    def create(cls, first_name: str, last_name: str, email: str) -> User:
        user = cls(first_name=first_name, last_name=last_name, email=email)
        user.events.append(
            UserCreated(user.id, user.email, user.full_name, user.created_date)
        )
        return user

    def __post_init__(self) -> None:
        norm_fname = self.first_name.strip().title()
        norm_lname = self.last_name.strip().title()

        if not norm_fname or not norm_lname:
            raise DomainValidationError("User", ["name fields cannot be empty"])
        self.first_name = norm_fname
        self.last_name = norm_lname

        try:
            _email = validate_email(self.email, check_deliverability=False)
            self.email = _email.normalized
        except EmailNotValidError as e:
            raise DomainValidationError("User", [f"Invalid email: {e}"])

    def to_summary(self) -> UserSummary:
        return UserSummary(
            self.first_name,
            self.last_name,
            self.email,
            self.last_login,
            self.modified_date,
            self.created_date,
            self.status,
            self.id,
        )

    def _touch(self) -> datetime:
        self.modified_date = datetime.now(UTC)
        return self.modified_date

    def update_first_name(self, name: str) -> None:
        norm_name = name.strip().title()
        if not norm_name:
            raise DomainValidationError("User", ["first name cannot be empty"])
        self.first_name = norm_name
        self._touch()

    def update_last_name(self, name: str) -> None:
        norm_name = name.strip().title()
        if not norm_name:
            raise DomainValidationError("User", ["last name cannot be empty"])
        self.last_name = norm_name
        self._touch()

    def update_email(self, email: str) -> None:
        try:
            _email = validate_email(email, check_deliverability=False)
            if _email.normalized == self.email:
                return
            self.email = _email.normalized
            self._touch()
        except EmailNotValidError as e:
            raise DomainValidationError("User", [f"Invalid email: {e}"])

    def update_status(self, status: UserStatus) -> None:
        if status == self.status:
            return

        self.status = status
        mod_date = self._touch()

        self.events.append(
            UserStatusChanged(
                user_id=self.id,
                email=self.email,
                full_name=self.full_name,
                new_status=self.status,
                modified_date=mod_date,
            )
        )

    def update_password_hash(self, password_hash: str) -> None:
        had_password: bool = self.password_hash is not None
        self.password_hash: str = password_hash
        mod_date: datetime = self._touch()
        if had_password:
            event = UserPasswordReset(
                user_id=self.id,
                email=self.email,
                full_name=self.full_name,
                reqested_date=mod_date,
            )
            self.events.append(event)

    def __hash__(self):
        return hash(self.id)
