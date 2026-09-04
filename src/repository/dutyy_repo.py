from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import dutyy_table, project_user_table, projects_table
from src.domain.dutyy import Dutyy
from src.logger import get_logger
from src.repository.abstract_repo import (
    AbstractRepository,
    Operation,
    RepoError,
    assert_managed,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, Select
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DutyRepo(AbstractRepository[Dutyy]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[Dutyy] = set()

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[Dutyy]:
        offset_value = (page - 1) * page_size

        stmt: Select[tuple[Dutyy]] = (
            select(Dutyy)
            .order_by(dutyy_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results: Result[tuple[Dutyy]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        dutyys: Sequence[Dutyy] = results.scalars().all()
        self.seen.update(dutyys)

        return list(dutyys)

    async def delete(self, entity: Dutyy) -> None:
        assert_managed(self._session, entity)

        try:
            await self._session.delete(entity)
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
        assert_managed(self._session, entity)

        try:
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
        stmt: Select[tuple[Dutyy]] = select(Dutyy).where(dutyy_table.c.id == dutyy_id)

        try:
            result: Result[tuple[Dutyy]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        dutyy: Dutyy | None = result.scalars().one_or_none()

        if dutyy is not None:
            self.seen.add(dutyy)

        return dutyy

    async def get_by_id_with_owner(
        self, dutyy_id: UUID, owner_id: UUID
    ) -> Dutyy | None:
        stmt: Select[tuple[Dutyy]] = (
            select(Dutyy)
            .where(dutyy_table.c.id == dutyy_id)
            .join(projects_table, projects_table.c.id == dutyy_table.c.project_id)
            .where(projects_table.c.owner_id == owner_id)
        )

        try:
            results: Result[tuple[Dutyy]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        dutyy: Dutyy | None = results.scalars().one_or_none()

        if dutyy is not None:
            self.seen.add(dutyy)

        return dutyy

    async def search_by_name(self, dutyy_name: str, user_id: UUID) -> list[Dutyy]:
        stmt: Select[tuple[Dutyy]] = (
            select(Dutyy)
            .join(
                project_user_table,
                dutyy_table.c.project_id == project_user_table.c.project_id,
            )
            .where(project_user_table.c.user_id == user_id)
            .where(dutyy_table.c.title.ilike(f"%{dutyy_name}%"))
        )

        try:
            results: Result[tuple[Dutyy]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        dutyys: Sequence[Dutyy] = results.scalars().all()
        self.seen.update(dutyys)

        return list(dutyys)

    async def get_by_project_id(self, project_id: UUID) -> list[Dutyy]:
        stmt: Select[tuple[Dutyy]] = select(Dutyy).where(
            dutyy_table.c.project_id == project_id
        )

        try:
            results: Result[tuple[Dutyy]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        dutyys: Sequence[Dutyy] = results.scalars().all()
        self.seen.update(dutyys)

        return list(dutyys)
