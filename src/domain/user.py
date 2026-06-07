from datetime import datetime, UTC
from dataclasses import dataclass, field, asdict
from uuid import UUID, uuid7
from typing import Any

from src.domain.enums import UserStatus
from src.domain.exceptions import DomainValidationError
from src.domain.events import UserCreated, UserPasswordReset, ProjectAssigned


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
