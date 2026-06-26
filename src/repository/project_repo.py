from __future__ import annotations
from typing import TYPE_CHECKING, Any, Sequence
from enum import StrEnum, auto

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import select, update, delete, insert

from src.repository.abstract_repo import AbstractRepository, Operation
from src.db.orm import projects_table, project_user_table
from src.domain.project import Project
from src.domain.exceptions import ProjectAlreadyExistsError
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import Select, RowMapping, Result, Delete
    from uuid import UUID


logger = get_logger(__name__)


class ProjectRepoErrorEvents(StrEnum):
    DB_UNAVAILBLE = auto()
    PROJECT_ADD_CONFLICT = auto()
    PROJECT_UPDATE_ERROR = auto()
    PROJECT_DELETE_ERROR = auto()


class ProjectRepo(AbstractRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[Project] = set()

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
        delete_stmt: Delete = delete(projects_table).where(
            projects_table.c.id == entity.id
        )

        try:
            await self._session.execute(delete_stmt)
            await self._session.flush()
            self.seen.add(entity)
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
        stmt = insert(project_user_table).values(
            project_id=entity.id, user_id=entity.owner_id
        )

        try:
            await self._session.flush()
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError as e:
            logger.error(
                event=ProjectRepoErrorEvents.PROJECT_ADD_CONFLICT,
                project_id=entity.id,
            )
            raise ProjectAlreadyExistsError(entity.name) from e
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.ADD)
            raise

    async def update(self, entity: Project) -> None:
        data: dict[str, Any] = entity.to_dict()
        data.pop("dutyys", None)
        stmt = (
            update(projects_table)
            .where(projects_table.c.id == entity.id)
            .values(**data)
        )

        try:
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError as e:
            logger.error(
                event=ProjectRepoErrorEvents.PROJECT_UPDATE_ERROR, project_id=entity.id
            )
            raise ProjectAlreadyExistsError(entity.name) from e
        except OperationalError:
            logger.error(
                event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.UPDATE
            )
            raise

    async def get_by_id(self, project_id: UUID) -> Project | None:
        stmt: Select[Any] = select(projects_table).where(
            projects_table.c.id == project_id
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        if row is None:
            return

        project = Project(**row)
        self.seen.add(project)

        return project

    async def search_by_name(self, project_name: str, owner_id: UUID) -> list[Project]:
        stmt: Select[Any] = (
            select(projects_table)
            .where(projects_table.c.name.ilike(f"%{project_name}%"))
            .where(projects_table.c.owner_id == owner_id)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()

        return [Project(**row) for row in rows]

    async def get_by_owner_id(self, owner_id: UUID) -> list[Project]:
        stmt: Select[Any] = select(projects_table).where(
            projects_table.c.owner_id == owner_id
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()

        return [Project(**row) for row in rows]

    async def get_projects_by_user_id(self, user_id: UUID) -> list[Project]:
        stmt: Select[Any] = (
            select(projects_table)
            .join(
                project_user_table,
                projects_table.c.id == project_user_table.c.project_id,
            )
            .where(project_user_table.c.user_id == user_id)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=ProjectRepoErrorEvents.DB_UNAVAILBLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()

        return [Project(**row) for row in rows]
