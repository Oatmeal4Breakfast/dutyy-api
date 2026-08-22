import hashlib
import secrets
from uuid import UUID
from typing import TypedDict, cast
from dataclasses import dataclass, asdict
from enum import StrEnum, auto
from datetime import datetime, timedelta, UTC


class DeviceCodeStatus(StrEnum):
    PENDING = auto()
    APPROVED = auto()
    CONSUMED = auto()


CHAR_SET = "BCDFGHJKLMNPQRSTVWXYZ23456789"


class DeviceCodeDict(TypedDict):
    hashed_device_code: str
    user_code: str | None
    status: DeviceCodeStatus
    expires_at: datetime
    user_id: UUID | None


@dataclass
class DeviceCode:
    hashed_device_code: str
    user_code: str
    status: DeviceCodeStatus
    expires_at: datetime
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
    def issue(cls, expires_at: datetime | None = None) -> tuple[str, "DeviceCode"]:
        raw_code: str = secrets.token_urlsafe(32)
        return raw_code, cls(
            hashed_device_code=cls.hash_device_code(raw_code),
            user_code=cls.generate_user_code(),
            status=DeviceCodeStatus.PENDING,
            expires_at=expires_at
            if expires_at is not None
            else (datetime.now(UTC) + timedelta(minutes=15)),
        )

    def to_dict(self) -> DeviceCodeDict:
        return cast(DeviceCodeDict, asdict(self))

    def is_expired(self) -> bool:
        return datetime.now(UTC) > self.expires_at

    def mark_approved(self, user_id: UUID) -> None:
        self.status = DeviceCodeStatus.APPROVED
        self.user_id = user_id

    def mark_consumed(self) -> None:
        self.status = DeviceCodeStatus.CONSUMED
