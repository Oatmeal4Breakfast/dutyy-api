from datetime import datetime, UTC
from uuid import UUID, uuid7
from typing import Any
from dataclasses import dataclass, field, asdict

from src.domain.exceptions import DomainValidationError


@dataclass(frozen=True)
class APIKey:
    user_id: UUID
    key_hash: str
    name: str
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

        object.__setattr__(self, "key_hash", norm_hash)
        object.__setattr__(self, "name", norm_name)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
