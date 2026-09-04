from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import dutyy_table, project_user_table, projects_table
from src.domain.dutyy import Dutyy
from src.logger import get_logger
from src.repository.abstract_repo import AbstractRepository, Operation, RepoError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, RowMapping, Select
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DutyRepo(AbstractRepository[Dutyy]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[Dutyy] = set()

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
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [Dutyy(**row) for row in rows]

    async def delete(self, entity: Dutyy) -> None:
        stmt = delete(dutyy_table).where(dutyy_table.c.id == entity.id)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

    async def add(self, entity: Dutyy) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                dutyy_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: Dutyy) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt = update(dutyy_table).where(dutyy_table.c.id == entity.id).values(**data)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                dutyy_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, dutyy_id: UUID) -> Dutyy | None:
        stmt: Select[Any] = select(dutyy_table).where(dutyy_table.c.id == dutyy_id)

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return Dutyy(**row) if row is not None else None

    async def get_by_id_with_owner(
        self, dutyy_id: UUID, owner_id: UUID
    ) -> Dutyy | None:
        stmt: Select = (
            select(Dutyy)
            .where(dutyy_table.c.id == dutyy_id)
            .join(projects_table, projects_table.c.id == dutyy_table.c.project_id)
            .where(projects_table.c.owner_id == owner_id)
        )

        try:
            results: Result = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return results.unique().scalar_one_or_none()

    async def search_by_name(self, dutyy_name: str, user_id: UUID) -> list[Dutyy]:
        stmt: Select[Any] = (
            select(dutyy_table)
            .join(
                project_user_table,
                dutyy_table.c.project_id == project_user_table.c.project_id,
            )
            .where(project_user_table.c.user_id == user_id)
            .where(dutyy_table.c.title.ilike(f"%{dutyy_name}%"))
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()

        return [Dutyy(**row) for row in rows]

    async def get_by_project_id(self, project_id: UUID) -> list[Dutyy]:
        stmt: Select[Any] = select(dutyy_table).where(
            dutyy_table.c.project_id == project_id
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [Dutyy(**row) for row in rows]
