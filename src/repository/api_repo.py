from __future__ import annotations
from typing import TYPE_CHECKING, Any, Sequence
from enum import StrEnum, auto
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.repository.abstract_repo import Operation
from src.domain.api import APIKey
from src.db.orm import api_key_table
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import Select, Update, Result, RowMapping
    from uuid import UUID

logger = get_logger(__name__)


class APIRepoErrorEvents(StrEnum):
    DB_UNAVAILABLE = auto()
    API_ADD_CONFLICT = auto()
    API_UPDATE_ERROR = auto()


class APIRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[APIKey] = set()

    async def get_by_user_id(self, user_id: UUID) -> list[APIKey]:
        stmt: Select[Any] = select(api_key_table).where(
            api_key_table.c.user_id == user_id
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=APIRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = result.mappings().all()

        return [APIKey(**row) for row in rows]

    async def add(self, entity: APIKey) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=APIRepoErrorEvents.API_ADD_CONFLICT,
                op=Operation.ADD,
                api_key_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=APIRepoErrorEvents.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: APIKey) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt: Update = (
            update(api_key_table).where(api_key_table.c.id == entity.id).values(**data)
        )

        try:
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=APIRepoErrorEvents.API_UPDATE_ERROR,
                op=Operation.UPDATE,
                api_key_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=APIRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise
