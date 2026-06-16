from __future__ import annotations
from typing import TYPE_CHECKING, Any, Sequence
from enum import StrEnum, auto

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import select, update, delete

from src.repository.abstract_repository import AbstractRepository, Operation
from src.db.orm import projects_table
from src.domain.project import Project
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import Select, RowMapping, Result, Delete


logger = get_logger(__name__)


class ProjectRepoErrorEvents(StrEnum):
    DB_UNAVAILBLE = auto()
    PROJECT_ADD_CONFLICT = auto()
    PROJECT_UPDATE_ERROR = auto()
    PROJECT_DELETE_ERROR = auto()


class ProjectRepo(AbstractRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[Project]:
        offset_value: int = (page - 1) * page_size

        stmt: Select[Any] = (
            select(projects_table)
            .order_by(projects_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [Project(**row) for row in rows]

    async def delete(self, entity: Project) -> None:
        stmt: Delete = delete(projects_table).where(projects_table.c.id == entity.id)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=ProjectRepoErrorEvents.PROJECT_DELETE_ERROR, project_id=entity.id
            )
            raise
        except OperationalError:
            logger.error(
                event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.DELETE
            )
            raise

    async def add(self, entity: Project) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=ProjectRepoErrorEvents.PROJECT_ADD_CONFLICT,
                project_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.ADD)
            raise

    async def update(self, entity: Project) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt = (
            update(projects_table)
            .where(projects_table.c.id == entity.id)
            .values(**data)
        )

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=ProjectRepoErrorEvents.PROJECT_UPDATE_ERROR, project_id=entity.id
            )
            raise
        except OperationalError:
            logger.error(
                event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.UPDATE
            )
