from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence
from enum import StrEnum, auto

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import update, delete, select

from src.repository.abstract_repository import AbstractRepository, Operation
from src.db.orm import users_table
from src.domain.user import User
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from uuid import UUID
    from sqlalchemy import Select, Result, RowMapping


logger = get_logger(__name__)


class UserRepoErrorEvents(StrEnum):
    DB_UNAVAILABLE = auto()
    USER_ADD_CONFLICT = auto()
    USER_UPDATE_ERROR = auto()
    USER_DELETE_ERROR = auto()


class UserRepo(AbstractRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[User]:
        offset_value: int = (page - 1) * page_size

        stmt: Select[Any] = (
            select(users_table)
            .order_by(users_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=UserRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = results.mappings().all()
        return [User(**row) for row in rows]

    async def delete(self, entity: User) -> None:
        stmt = delete(users_table).where(users_table.c.id == entity.id)

        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(event=UserRepoErrorEvents.USER_DELETE_ERROR, user_id=entity.id)
            raise
        except OperationalError:
            logger.error(event=UserRepoErrorEvents.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

    async def add(self, entity: User) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=UserRepoErrorEvents.USER_ADD_CONFLICT,
                user_id=entity.id,
                user_name=entity.full_name,
            )
            raise
        except OperationalError:
            logger.error(event=UserRepoErrorEvents.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: User) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt = update(users_table).where(users_table.c.id == entity.id).values(**data)
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(event=UserRepoErrorEvents.USER_UPDATE_ERROR, user_id=entity.id)
            raise
        except OperationalError:
            logger.error(event=UserRepoErrorEvents.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt: Select[tuple[Any]] = select(users_table).where(
            users_table.c.id == user_id
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=UserRepoErrorEvents.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return User(**row) if row is not None else None
