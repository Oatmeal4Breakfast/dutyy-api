from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass, asdict
from typing import TYPE_CHECKING, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import DeviceCodeCollisionError
from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.config import DeviceAuthConfig
from src.logger import get_logger
from src.db.uow import AbstractUnitOfWork

if TYPE_CHECKING:
    from uuid import UUID
    from src.bus.bus import EventBus

logger = get_logger(__name__)


@dataclass(frozen=True)
class DeviceCodeClientData:
    raw_device_code: str
    user_code: str
    expires_at: datetime
    verification_uri: str

    def to_dict(self) -> dict[str, str | datetime]:
        return asdict(self)


@dataclass(frozen=True)
class DeviceAuthError:
    user_code: str | None = None
    user_id: UUID | None = None
    error: str | None = None


class DeviceAuthService:
    def __init__(
        self,
        config: DeviceAuthConfig,
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
    ) -> None:
        self._uow_factory: Callable = uow_factory
        self.max_attempts: int = config.max_attempts
        self.verification_uri: str = config.verification_base_uri

    async def approve(
        self, user_code: str, user_id: UUID
    ) -> DeviceCode | DeviceAuthError:
        async with self._uow_factory() as uow:
            device_code: (
                DeviceCode | None
            ) = await uow.device_auth.get_code_by_user_code(user_code)
            if device_code is None:
                logger.warning(
                    event="device_code_not_found",
                    user_code=user_code,
                    user_id=str(user_id),
                )
                return DeviceAuthError(
                    user_code=user_code, user_id=user_id, error="device_code not found"
                )

            if (
                device_code.status != DeviceCodeStatus.PENDING
                or device_code.is_expired()
            ):
                logger.warning(
                    event="device_code_not_eligible_for_approval",
                    user_code=user_code,
                    user_id=str(user_id),
                )
                return DeviceAuthError(
                    user_code=user_code,
                    user_id=user_id,
                    error="device_code not eligible for approval",
                )

            device_code.mark_approved(user_id)

            await uow.device_auth.update(device_code)
            await uow.commit()

            return device_code

    async def start(self) -> DeviceCodeClientData:
        for _ in range(self.max_attempts):
            raw, hashed = DeviceCode.issue()
            async with self._uow_factory() as uow:
                try:
                    await uow.device_auth.add(hashed)
                    await uow.commit()
                    return DeviceCodeClientData(
                        raw_device_code=raw,
                        user_code=hashed.user_code,
                        expires_at=hashed.expires_at,
                        verification_uri=self.verification_uri,
                    )
                except IntegrityError:
                    continue
        raise DeviceCodeCollisionError()
