import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.domain.exceptions import DomainValidationError


@dataclass(frozen=True)
class SessionPolicy:
    idle_ttl: timedelta
    absolute_ttl: timedelta
    touch_interval: timedelta

    def __post_init__(self) -> None:
        if not (
            self.touch_interval > timedelta(0)
            and self.touch_interval < self.idle_ttl
            and self.idle_ttl <= self.absolute_ttl
        ):
            raise DomainValidationError(
                "SessionPolicy", ["Session policy contains timing conflicts"]
            )


class WebSession(Base):
    __tablename__ = "web_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    idle_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

    def __post_init__(self) -> None:
        norm_hash: str = self.token_hash.strip()
        if not norm_hash:
            raise DomainValidationError("WebSession", ["token hash cannot be empty"])

        self.token_hash = norm_hash

        if self.created_at > self.last_seen_at:
            raise DomainValidationError(
                "WebSession", ["created_at cannot be after last_seen_at"]
            )
        if self.last_seen_at >= self.idle_expires_at:
            raise DomainValidationError(
                "WebSession", ["last_seen_at must be before idle_expires_at"]
            )
        if self.idle_expires_at > self.absolute_expires_at:
            raise DomainValidationError(
                "WebSession",
                ["idle_expires_at cannot be after absolute_expires_at"],
            )

    @classmethod
    def issue(
        cls, user_id: UUID, policy: SessionPolicy, now: datetime | None = None
    ) -> tuple[str, "WebSession"]:
        raw_token: str = secrets.token_urlsafe(32)
        hashed_token: str = cls.hash_token(raw_token)
        if now is None:
            now = datetime.now(UTC)

        return raw_token, cls(
            token_hash=hashed_token,
            user_id=user_id,
            idle_expires_at=now + policy.idle_ttl,
            absolute_expires_at=now + policy.absolute_ttl,
            last_seen_at=now,
            created_at=now,
        )

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def touch(self, policy: SessionPolicy, now: datetime | None = None) -> None:
        if now is None:
            now = datetime.now(UTC)
        if not self.is_active(now):
            raise DomainValidationError("WebSession", [f"token {self.id} is inactive"])

        throttle: timedelta = now - self.last_seen_at

        if throttle < policy.touch_interval:
            return

        extended_idle = now + policy.idle_ttl
        self.last_seen_at = now

        if extended_idle >= self.absolute_expires_at:
            self.idle_expires_at = self.absolute_expires_at
        else:
            self.idle_expires_at = extended_idle

    def revoke(self, now: datetime | None = None) -> None:
        if self.revoked_at is not None:
            return
        if now is None:
            now = datetime.now(UTC)
        self.revoked_at = now

    def is_active(self, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now(UTC)
        return (
            self.revoked_at is None
            and now < self.absolute_expires_at
            and now < self.idle_expires_at
        )
