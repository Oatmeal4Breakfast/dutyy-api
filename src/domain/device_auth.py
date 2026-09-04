import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from uuid import UUID


class DeviceCodeStatus(StrEnum):
    PENDING = auto()
    APPROVED = auto()
    CONSUMED = auto()


class KeyLifetime(StrEnum):
    THIRTY_DAYS = auto()
    NINETY_DAYS = auto()
    ONE_YEAR = auto()

    @property
    def ttl(self) -> timedelta:
        return {
            KeyLifetime.THIRTY_DAYS: timedelta(days=30),
            KeyLifetime.NINETY_DAYS: timedelta(days=90),
            KeyLifetime.ONE_YEAR: timedelta(days=365),
        }[self]


CHAR_SET = "BCDFGHJKLMNPQRSTVWXYZ23456789"


def _default_key_name() -> str:
    return f"cli-{secrets.token_hex(3)}"


@dataclass
class DeviceCode:
    hashed_device_code: str
    user_code: str
    status: DeviceCodeStatus
    expires_at: datetime
    key_name: str = field(default_factory=_default_key_name)
    key_lifetime: KeyLifetime = KeyLifetime.THIRTY_DAYS
    user_id: UUID | None = None

    @staticmethod
    def hash_device_code(code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def generate_user_code() -> str:
        part_1: str = "".join(secrets.choice(CHAR_SET) for _ in range(4))
        part_2: str = "".join(secrets.choice(CHAR_SET) for _ in range(4))
        return f"{part_1}-{part_2}"

    @classmethod
    def issue(
        cls,
        expires_at: datetime | None = None,
        key_name: str | None = None,
        key_lifetime: KeyLifetime = KeyLifetime.THIRTY_DAYS,
    ) -> tuple[str, "DeviceCode"]:
        raw_code: str = secrets.token_urlsafe(32)
        return raw_code, cls(
            hashed_device_code=cls.hash_device_code(raw_code),
            user_code=cls.generate_user_code(),
            status=DeviceCodeStatus.PENDING,
            expires_at=expires_at
            if expires_at is not None
            else (datetime.now(UTC) + timedelta(minutes=15)),
            key_name=key_name if key_name is not None else _default_key_name(),
            key_lifetime=key_lifetime,
        )

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def mark_approved(self, user_id: UUID) -> None:
        self.status = DeviceCodeStatus.APPROVED
        self.user_id = user_id

    def mark_consumed(self) -> None:
        self.status = DeviceCodeStatus.CONSUMED
