import hashlib
import secrets
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid7

from src.domain.exceptions import DomainValidationError


@dataclass
class PasswordSetToken:
    user_id: UUID
    token_hash: str
    expires_at: datetime
    created_date: datetime
    used_at: datetime | None = None
    id: UUID = field(default_factory=uuid7)

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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

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
