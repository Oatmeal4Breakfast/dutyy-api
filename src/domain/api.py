from datetime import datetime, UTC
from uuid import UUID, uuid7
from typing import Any
from dataclasses import dataclass, field, asdict
from enum import StrEnum, auto

from src.domain.exceptions import DomainValidationError


class APIKeyStatus(StrEnum):
    ACTIVE = auto()
    INACTIVE = auto()


@dataclass
class APIKey:
    key_hash: str
    name: str
    user_id: UUID
    status: APIKeyStatus = field(default=APIKeyStatus.ACTIVE)
    last_used: datetime | None = None
    expires_at: datetime | None = None
    created_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: UUID = field(default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_hash = self.key_hash.strip()
        norm_name = self.name.strip()

        if not norm_hash:
            raise DomainValidationError("APIKey", ["key hash cannot be empty"])
        if not norm_name:
            raise DomainValidationError("APIKey", ["name cannot be empty"])

        self.key_hash = norm_hash
        self.name = norm_name

    def mark_inactive(self) -> None:
        self.status = APIKeyStatus.INACTIVE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def __hash__(self):
        return hash(self.id)
