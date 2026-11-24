from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db.uow import AbstractUnitOfWork
from src.domain.api import APIKey, APIKeyStatus, APIKeySummary
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
            await uow.api.mark_expired_for_user(
                user_id=user_id,
                key_name=key.name,
                now=datetime.now(UTC),
            )
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

            if key is None or key.status != APIKeyStatus.ACTIVE:
                return None

            now = datetime.now(UTC)
            if key.expires_at is None:
                return None

            if key.is_expired(now):
                await uow.api.mark_expired(api_key_id=key.id, user_id=key.user_id)
                await uow.commit()
                return None

            if key.touch():
                await uow.api.update(key)
                await uow.commit()

        return key

    async def revoke(self, user_id: UUID, key_id: UUID) -> None:
        async with self._uow_factory() as uow:
            key: APIKey | None = await uow.api.get_by_id(
                key_id=key_id, owner_id=user_id
            )

            if key is None:
                return None

            if key.status == APIKeyStatus.ACTIVE and key.is_expired():
                await uow.api.mark_expired(
                    api_key_id=key.id,
                    user_id=user_id,
                )
            elif key.status == APIKeyStatus.ACTIVE:
                key.mark_inactive()
                await uow.api.update(key)
            await uow.commit()

        logger.info(event="api_key_revoked", key_id=str(key_id), user_id=str(user_id))

    async def get_keys_by_user_id(self, user_id: UUID) -> list[APIKeySummary]:
        async with self._uow_factory() as uow:
            expired_count = await uow.api.mark_expired_for_user(
                user_id=user_id, now=datetime.now(UTC)
            )
            keys: list[APIKeySummary] = await uow.api.get_by_user_id(user_id=user_id)
            if expired_count:
                await uow.commit()
            logger.info(event="retrieved_keys", count=len(keys), user_id=str(user_id))
            return keys
