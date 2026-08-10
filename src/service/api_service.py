from __future__ import annotations

from datetime import timedelta, datetime, UTC
from typing import TYPE_CHECKING, Callable

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.domain.api import APIKey, APIKeyStatus
from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger

if TYPE_CHECKING:
    from uuid import UUID
    from src.bus.bus import EventBus

logger = get_logger(__name__)


class APIService:
    def __init__(
        self,
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
    ) -> None:
        self._uow_factory: Callable = uow_factory

    async def issue_new_key(self, user_id: UUID, key_name: str, ttl: timedelta) -> str:
        raw, key = APIKey.issue(user_id, name=key_name, ttl=ttl)

        async with self._uow_factory() as uow:
            await uow.api.add(key)
            await uow.commit()
            logger.info(
                event="new_api_key_generated", user=str(user_id), key_name=key_name
            )

        return raw

    async def verify(self, raw_key: str) -> APIKey | None:
        hash: str = APIKey.hash_key(raw_key)
        async with self._uow_factory() as uow:
            key: APIKey | None = await uow.api.get_by_hash(hash=hash)

            if (
                key is None
                or key.status != APIKeyStatus.ACTIVE
                or (key.expires_at is None or datetime.now(UTC) > key.expires_at)
            ):
                return None

            key.touch()
            await uow.api.update(key)
            await uow.commit()

        return key

    async def revoke(self, user_id: UUID, key_id: UUID) -> None:
        async with self._uow_factory() as uow:
            key: APIKey | None = await uow.api.get_by_id(key_id=key_id)

            if key is None:
                return None

            if key.user_id != user_id:
                logger.error(
                    event="access_denied", user_id=str(user_id), key_id=str(key_id)
                )
                return

            key.mark_inactive()

            await uow.api.update(key)
            await uow.commit()

        logger.info(event="api_key_revoked", key_id=str(key_id), user_id=str(user_id))
