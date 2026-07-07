from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import update, delete, select

from src.repository.abstract_repo import AbstractRepository, Operation, RepoError
from src.domain.user import UserSummary, User
from src.db.orm import users_table, project_user_table
from src.domain.exceptions import UserAlreadyExistsError
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from uuid import UUID
    from sqlalchemy import Select, Result, RowMapping, Delete


logger = get_logger(__name__)


class UserRepo(AbstractRepository[User, UserSummary]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[User] = set()

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[UserSummary]:
        offset_value: int = (page - 1) * page_size

        stmt: Select[Any] = (
            select(
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.email,
                users_table.c.last_login,
                users_table.c.modified_date,
                users_table.c.created_date,
                users_table.c.status,
                users_table.c.id,
            )
            .order_by(users_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [UserSummary(**row) for row in rows]

    async def delete(self, entity: User) -> None:
        self.seen.add(entity)
        stmt: Delete = delete(users_table).where(users_table.c.id == entity.id)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.DELETE,
                user_id=entity.id,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

    async def add(self, entity: User) -> None:
        self.seen.add(entity)
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError as e:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                user_id=entity.id,
                user_name=entity.full_name,
            )
            raise UserAlreadyExistsError(entity.email) from e
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: User) -> None:
        self.seen.add(entity)
        data: dict[str, Any] = entity.to_dict()
        stmt = update(users_table).where(users_table.c.id == entity.id).values(**data)
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError as e:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                user_id=entity.id,
            )
            raise UserAlreadyExistsError(entity.email) from e
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt: Select[Any] = select(users_table).where(users_table.c.id == user_id)

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        if row is None:
            return

        user: User = User(**row)
        self.seen.add(user)

        return user

    async def get_users_by_project_id(self, project_id: UUID) -> list[UserSummary]:
        stmt: Select[Any] = (
            select(
                users_table.c.first_name,
                users_table.c.last_name,
                users_table.c.email,
                users_table.c.last_login,
                users_table.c.modified_date,
                users_table.c.created_date,
                users_table.c.status,
                users_table.c.id,
            )
            .join(project_user_table, users_table.c.id == project_user_table.c.user_id)
            .where(project_user_table.c.project_id == project_id)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [UserSummary(**row) for row in rows]

    async def get_user_by_email(self, email: str) -> User | None:
        stmt: Select[Any] = select(users_table).where(users_table.c.email == email)

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)

        row: RowMapping | None = result.mappings().one_or_none()

        return User(**row) if row is not None else None
