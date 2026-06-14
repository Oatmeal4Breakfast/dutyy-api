from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy import Select, update, delete

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.abstract_repository import AbstractRepository
from src.db.orm import users_table
from src.domain.user import User
from src.logger import get_logger

logger = get_logger(__name__)


class UserRepo(AbstractRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: User) -> None:
        logger.debug(event="user_added", user_id=entity.id, user_name=entity.full_name)

        self._session.add(entity)

        try:
            self._session.flush()
        except IntegrityError:
            logger.error(
                event="user_added_conflict",
                user_id=entity.id,
                user_name=entity.full_name,
            )
            raise
        except OperationalError:
            logger.error(event="db_unavailable", op="user_add")
            raise

    async def get_all(self, page: int = 1, page_size: int = 100) -> list[User]:
        offset_value = (page - 1) * page_size

        stmt = (
            Select(users_table)
            .order_by(users_table.c.id)
            .limit(page_size)
            .offset(offset_value)
        )

        try:
            results = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event="db_unavailable", op="user_get")
            raise

        rows = results.mappings().all()
        return [User(**row) for row in rows]
