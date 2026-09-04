import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.domain.exceptions import DomainValidationError


class PasswordSetToken(Base):
    __tablename__ = "password_token"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default_factory=uuid7)

    @classmethod
    def issue(cls, user_id: UUID, ttl: timedelta) -> tuple[str, "PasswordSetToken"]:
        raw_token: str = secrets.token_urlsafe(32)
        hashed_token: str = cls.hash_token(raw_token)
        now: datetime = datetime.now(UTC)
        return raw_token, cls(
            user_id=user_id,
            token_hash=hashed_token,
            created_date=now,
            expires_at=ttl + now,
        )

    @staticmethod
    def hash_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    def is_expired(self, now: datetime | None = None) -> bool:
        now: datetime = now or datetime.now(UTC)
        return now > self.expires_at

    def is_used(self) -> bool:
        return self.used_at is not None

    def consume(self) -> None:
        if self.is_used() or self.is_expired():
            raise DomainValidationError(
                entity="PasswordSetToken",
                errors=[
                    f"""
                        PasswordSetToken with id {self.id}
                        is expired or has been consumed.
                    """
                ],
            )
        self.used_at = datetime.now(UTC)
