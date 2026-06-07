from datetime import datetime, UTC
from uuid import UUID, uuid7
from typing import Any
from dataclasses import dataclass, field, asdict
from email_validator import validate_email, EmailNotValidError

from src.domain.enums import UserStatus
from src.domain.exceptions import DomainValidationError
from src.domain.events import UserPasswordReset


@dataclass
class User:
    first_name: str
    last_name: str
    email: str
    hashed_password: str | None = None
    last_login: datetime | None = None
    modified_date: datetime | None = None
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    events: list = field(default_factory=list, init=False, repr=False)
    status: UserStatus = field(default=UserStatus.ACTIVE)
    id: UUID = field(default_factory=uuid7)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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

    def _mark_inactive(self) -> None:
        self.status = UserStatus.INACTIVE
        self._touch()

    def _mark_active(self) -> None:
        self.status = UserStatus.ACTIVE
        self._touch()

    def _mark_blocked(self) -> None:
        self.status = UserStatus.BLOCKED
        self._touch()

    def update_status(self, status: UserStatus) -> None:
        if status == self.status:
            return

        match status:
            case UserStatus.ACTIVE:
                self._mark_active()
            case UserStatus.INACTIVE:
                self._mark_inactive()
            case UserStatus.BLOCKED:
                self._mark_blocked()
            case _:
                raise DomainValidationError(
                    "User", [f"{status} is not a valid transition"]
                )

    def update_hashed_password(self, hashed_password: str) -> None:
        self.hashed_password = hashed_password
        mod_date = self._touch()
        self.events.append(UserPasswordReset(user_id=self.id, request_date=mod_date))
