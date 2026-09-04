from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import project_user_table
from src.domain.exceptions import UserAlreadyExistsError
from src.domain.user import User, UserStatus, UserSummary
from src.logger import get_logger
from src.repository.abstract_repo import (
    AbstractRepository,
    Operation,
    RepoError,
    assert_managed,
)

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, RowMapping, Select
    from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger(__name__)


class UserRepo(AbstractRepository[User, UserSummary]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[User] = set()

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[UserSummary]:
        offset_value: int = (page - 1) * page_size

        stmt: Select[Any] = (
            select(
                User.first_name,
                User.last_name,
                User.email,
                User.last_login,
                User.modified_date,
                User.created_date,
                User.status,
                User.id,
            )
            .order_by(User.id)
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
        assert_managed(self._session, entity)

        try:
            await self._session.delete(entity)
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
        assert_managed(self._session, entity)

        try:
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
        stmt: Select[tuple[User]] = select(User).where(User.id == user_id)

        try:
            result: Result[tuple[User]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        user: User | None = result.scalars().one_or_none()

        if user is None:
            return

        self.seen.add(user)

        return user

    async def get_users_by_project_id(self, project_id: UUID) -> list[UserSummary]:
        stmt: Select[Any] = (
            select(
                User.first_name,
                User.last_name,
                User.email,
                User.last_login,
                User.modified_date,
                User.created_date,
                User.status,
                User.id,
            )
            .join(project_user_table, User.id == project_user_table.c.user_id)
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
        stmt: Select[tuple[User]] = select(User).where(User.email == email)

        try:
            result: Result[tuple[User]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        user: User | None = result.scalars().one_or_none()

        if user is not None:
            self.seen.add(user)

        return user

    async def get_active_user_by_email(self, email: str) -> User | None:
        stmt: Select[tuple[User]] = select(User).where(
            User.email == email, User.status == UserStatus.ACTIVE
        )

        try:
            result: Result[tuple[User]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        user: User | None = result.scalars().one_or_none()

        if user is not None:
            self.seen.add(user)

        return user
