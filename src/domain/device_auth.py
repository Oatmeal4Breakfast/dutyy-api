import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from enum import StrEnum, auto
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


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


class DeviceCode(Base):
    __tablename__ = "device_auth_code"

    hashed_device_code: Mapped[str] = mapped_column(String, primary_key=True)
    user_code: Mapped[str] = mapped_column(
        String, nullable=False, unique=True, index=True
    )
    status: Mapped[DeviceCodeStatus] = mapped_column(
        Enum(DeviceCodeStatus, name="devicecodestatus"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    key_name: Mapped[str] = mapped_column(
        String, nullable=False, default_factory=_default_key_name
    )
    key_lifetime: Mapped[KeyLifetime] = mapped_column(
        Enum(KeyLifetime, name="keylifetime"),
        nullable=False,
        default=KeyLifetime.THIRTY_DAYS,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, default=None
    )

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
