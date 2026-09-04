import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from uuid import UUID, uuid7

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
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


class APIKey(Base):
    __tablename__ = "api_keys"

    key_hash: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[APIKeyStatus] = mapped_column(
        Enum(APIKeyStatus, name="apikeystatus"),
        nullable=False,
        default=APIKeyStatus.ACTIVE,
    )
    last_used: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default_factory=lambda: datetime.now(UTC),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

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


Index(
    "uq_api_keys_active_name",
    APIKey.user_id,
    APIKey.name,
    unique=True,
    postgresql_where=(APIKey.status == APIKeyStatus.ACTIVE),
)
