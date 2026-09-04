from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import selectinload

from src.db.orm import project_user_table
from src.domain.exceptions import ProjectAlreadyExistsError
from src.domain.project import Project
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


class ProjectRepo(AbstractRepository[Project]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[Project] = set()

    def _select(self) -> Select[tuple[Project]]:
        return select(Project).options(selectinload(Project.dutyys))

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[Project]:
        offset_value: int = (page - 1) * page_size

        stmt: Select[tuple[Project]] = (
            self._select().order_by(Project.id).limit(page_size).offset(offset_value)
        )

        try:
            results: Result[tuple[Project]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        projects: Sequence[Project] = results.scalars().all()
        self.seen.update(projects)

        return list(projects)

    async def delete(self, entity: Project) -> None:
        assert_managed(self._session, entity)

        try:
            await self._session.delete(entity)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.DELETE,
                project_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.DELETE)
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
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                project_id=entity.id,
            )
            raise ProjectAlreadyExistsError(entity.name) from e
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: Project) -> None:
        assert_managed(self._session, entity)

        try:
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError as e:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                project_id=entity.id,
            )
            raise ProjectAlreadyExistsError(entity.name) from e
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, project_id: UUID, owner_id: UUID) -> Project | None:
        stmt: Select[tuple[Project]] = self._select().where(
            Project.id == project_id, Project.owner_id == owner_id
        )

        try:
            result: Result[tuple[Project]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        project: Project | None = result.scalars().one_or_none()

        if project is not None:
            self.seen.add(project)

        return project

    async def search_by_name(self, project_name: str, owner_id: UUID) -> list[Project]:
        stmt: Select[tuple[Project]] = (
            self._select()
            .where(Project.name.ilike(f"%{project_name}%"))
            .where(Project.owner_id == owner_id)
        )

        try:
            results: Result[tuple[Project]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        projects: Sequence[Project] = results.scalars().all()
        self.seen.update(projects)

        return list(projects)

    async def get_by_owner_id(self, owner_id: UUID) -> list[Project]:
        stmt: Select[tuple[Project]] = self._select().where(
            Project.owner_id == owner_id
        )

        try:
            results: Result[tuple[Project]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        projects: Sequence[Project] = results.scalars().all()
        self.seen.update(projects)

        return list(projects)

    async def get_projects_by_user_id(self, user_id: UUID) -> list[Project]:
        stmt: Select[tuple[Project]] = (
            self._select()
            .join(
                project_user_table,
                Project.id == project_user_table.c.project_id,
            )
            .where(project_user_table.c.user_id == user_id)
        )

        try:
            results: Result[tuple[Project]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        projects: Sequence[Project] = results.scalars().all()
        self.seen.update(projects)

        return list(projects)
