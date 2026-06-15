from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence
from enum import StrEnum, auto

from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError, OperationalError

from src.repository.abstract_repository import AbstractRepository, Operation
from src.db.orm import dutyy_table
from src.domain.dutyy import Dutyy
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from uuid import UUID
    from sqlalchemy import Select, RowMapping, Result

logger = get_logger(__name__)


class DutyyRepoErrorEvents(StrEnum):
    DB_UNAVAILABLE = auto()
    DUTYY_ADD_ERROR = auto()
    DUTYY_UPDATE_ERROR = auto()
    DUTYY_DELETE_ERROR = auto()


class DutyRepo(AbstractRepository[Dutyy]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[Dutyy]:
        offset_value = (page - 1) * page_size

        stmt: Select[Any] = (
            select(dutyy_table)
            .order_by(dutyy_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [Dutyy(**row) for row in rows]

    async def delete(self, entity: Dutyy) -> None:
        stmt = delete(dutyy_table).where(dutyy_table.c.id == entity.id)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=DutyyRepoErrorEvents.DUTYY_DELETE_ERROR,
                op=Operation.DELETE,
                dutyy_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

    async def add(self, entity: Dutyy) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=DutyyRepoErrorEvents.DUTYY_ADD_ERROR,
                op=Operation.ADD,
                dutyy_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: Dutyy) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt = update(dutyy_table).where(dutyy_table.c.id == entity.id).values(**data)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=DutyyRepoErrorEvents.DUTYY_UPDATE_ERROR,
                op=Operation.UPDATE,
                dutyy_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, dutyy_id: UUID) -> Dutyy | None:
        stmt: Select[Any] = select(dutyy_table).where(dutyy_table.c.id == dutyy_id)

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return Dutyy(**row) if row is not None else None

    async def get_by_name(self, dutyy_name: str) -> Dutyy | None:
        stmt: Select[Any] = select(dutyy_table).where(
            dutyy_table.c.title.like(dutyy_name)
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return Dutyy(**row) if row is not None else None

    async def get_by_project_id(self, project_id: UUID) -> list[Dutyy]:
        stmt: Select[Any] = select(dutyy_table).where(
            dutyy_table.c.project_id == project_id
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=DutyyRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
