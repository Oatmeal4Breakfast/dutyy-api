from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import api_key_table
from src.domain.api import APIKey, APIKeySummary
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError, assert_managed

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, RowMapping, Select
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class APIRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> list[APIKeySummary]:
        stmt: Select[Any] = select(
            api_key_table.c.id,
            api_key_table.c.name,
            api_key_table.c.status,
            api_key_table.c.created_date,
            api_key_table.c.last_used,
            api_key_table.c.expires_at,
        ).where(api_key_table.c.user_id == user_id)

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = result.mappings().all()

        return [APIKeySummary(**row) for row in rows]

    async def add(self, entity: APIKey) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                api_key_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: APIKey) -> None:
        assert_managed(self._session, entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                api_key_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_hash(self, hash: str) -> APIKey | None:
        stmt: Select[tuple[APIKey]] = select(APIKey).where(
            api_key_table.c.key_hash == hash
        )

        try:
            result: Result[tuple[APIKey]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()

    async def get_by_id(self, key_id: UUID) -> APIKey | None:
        stmt: Select[tuple[APIKey]] = select(APIKey).where(api_key_table.c.id == key_id)

        try:
            result: Result[tuple[APIKey]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()
