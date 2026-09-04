import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from uuid import UUID, uuid7

from src.domain.exceptions import DomainValidationError


class APIKeyStatus(StrEnum):
    ACTIVE = auto()
    INACTIVE = auto()


@dataclass(frozen=True)
class APIKeySummary:
    id: UUID
    name: str
    status: APIKeyStatus
    created_date: datetime
    last_used: datetime | None = None
    expires_at: datetime | None = None


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

    @classmethod
    def issue(cls, user_id: UUID, name: str, ttl: timedelta) -> tuple[str, "APIKey"]:
        raw_key: str = secrets.token_urlsafe(32)
        hashed_key: str = cls.hash_key(raw_key)
        now: datetime = datetime.now(UTC)
        return raw_key, cls(
            key_hash=hashed_key, name=name, user_id=user_id, expires_at=ttl + now
        )

    @staticmethod
    def hash_key(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def touch(self) -> None:
        self.last_used = datetime.now(UTC)

    def mark_inactive(self) -> None:
        self.status = APIKeyStatus.INACTIVE

    def __hash__(self):
        return hash(self.id)
