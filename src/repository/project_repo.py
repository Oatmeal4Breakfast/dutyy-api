from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence, cast

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import InstrumentedAttribute, joinedload

from src.db.orm import project_user_table, projects_table
from src.domain.exceptions import ProjectAlreadyExistsError
from src.domain.project import Project
from src.logger import get_logger
from src.repository.abstract_repo import AbstractRepository, Operation, RepoError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Delete, Result, RowMapping, Select
    from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger(__name__)


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
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
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
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                project_id=entity.id,
            )
            raise ProjectAlreadyExistsError(entity.name) from e
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, project_id: UUID) -> Project | None:
        stmt: Select[Any] = select(projects_table).where(
            projects_table.c.id == project_id
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        if row is None:
            return

        project = Project(**row)
        self.seen.add(project)

        return project

    async def get_by_id_with_dutyys(self, project_id: UUID) -> Project | None:
        dutyys_relationship = cast(InstrumentedAttribute[Any], Project.dutyys)

        stmt: Select[tuple[Project]] = (
            select(Project)
            .options(joinedload(dutyys_relationship))
            .where(projects_table.c.id == project_id)
        )

        try:
            result: Result = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        project: Project | None = result.unique().scalar_one_or_none()

        if project is not None:
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
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
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
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
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
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()

        return [Project(**row) for row in rows]
