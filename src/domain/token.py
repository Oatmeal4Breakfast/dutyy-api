import secrets
import hashlib
from typing import Any
from datetime import datetime, UTC, timedelta
from uuid import UUID, uuid7
from dataclasses import dataclass, field, asdict

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
    def issue(cls, user_id: UUID) -> tuple[str, "PasswordSetToken"]:
        raw_token: str = secrets.token_urlsafe(32)
        hashed_token: str = hashlib.sha256(raw_token.encode()).hexdigest()
        now: datetime = datetime.now(UTC)
        expires_at: datetime = now + timedelta(minutes=30)
        return raw_token, cls(
            user_id=user_id,
            token_hash=hashed_token,
            created_date=now,
            expires_at=expires_at,
        )

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
                    f"PasswordSetToken with id {self.id} is expired or has been consumed."
                ],
            )
        self.used_at = datetime.now(UTC)
