import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.domain.exceptions import DomainValidationError


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

    @classmethod
    def issue(
        cls, user_id: UUID, idle_expires: timedelta, absolute_expires: timedelta
    ) -> tuple[str, "WebSession"]:
        raw_token: str = secrets.token_urlsafe(32)
        hashed_token: str = cls.hash_token(raw_token)
        now: datetime = datetime.now(UTC)
        return raw_token, cls(
            token_hash=hashed_token,
            user_id=user_id,
            idle_expires_at=now + idle_expires,
            absolute_expires_at=now + absolute_expires,
            last_seen_at=now,
            created_at=now,
        )

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def touch(self, idle_expires: timedelta) -> None:
        now: datetime = datetime.now(UTC)
        if not self.is_active(now):
            raise DomainValidationError("WebSession", [f"token {self.id} is inactive"])

        throttle: timedelta = now - self.last_seen_at

        if throttle < timedelta(minutes=5):
            return

        self.last_seen_at = now
        self.idle_expires_at = now + idle_expires

    def revoke(self) -> None:
        if self.revoked_at is not None:
            return
        self.revoked_at = datetime.now(UTC)

    def is_active(self, now: datetime | None = None) -> bool:
        now: datetime = now or datetime.now(UTC)
        return (
            self.revoked_at is None
            and now < self.absolute_expires_at
            and now < self.idle_expires_at
        )
