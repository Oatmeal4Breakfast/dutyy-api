from __future__ import annotations

from typing import TYPE_CHECKING, Any
from enum import StrEnum, auto

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.repository.abstract_repo import Operation
from src.domain.token import PasswordSetToken
from src.db.orm import password_set_tokens_table
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import Result, RowMapping, Select, Update

logger = get_logger(__name__)


class PasswordSetTokenErrorEvents(StrEnum):
    DB_UNAVAILABLE = auto()
    TOKEN_ADD_CONFLICT = auto()
    TOKEN_UPDATE_CONFLICT = auto()


class PasswordSetTokenRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.seen: set[PasswordSetToken] = set()

    async def add(self, entity: PasswordSetToken) -> None:
        self._session.add(entity)
        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=PasswordSetTokenErrorEvents.TOKEN_ADD_CONFLICT,
                op=Operation.ADD,
                token_id=str(entity.id),
            )
            raise
        except OperationalError:
            logger.error(
                event=PasswordSetTokenErrorEvents.DB_UNAVAILABLE, op=Operation.ADD
            )
            raise

    async def get_by_hash(self, hash: str) -> PasswordSetToken | None:
        stmt: Select[Any] = select(password_set_tokens_table).where(
            password_set_tokens_table.c.token_hash == hash
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(
                event=PasswordSetTokenErrorEvents.DB_UNAVAILABLE, op=Operation.GET
            )
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        if row is None:
            return None

        token = PasswordSetToken(**row)
        self.seen.add(token)
        return token

    async def update(self, entity: PasswordSetToken) -> None:
        data: dict[str, Any] = entity.to_dict()
        stmt: Update = (
            update(password_set_tokens_table)
            .where(password_set_tokens_table.c.id == entity.id)
            .values(**data)
        )

        try:
            await self._session.execute(stmt)
            await self._session.flush()
            self.seen.add(entity)
        except IntegrityError:
            logger.error(
                event=PasswordSetTokenErrorEvents.TOKEN_UPDATE_CONFLICT,
                op=Operation.UPDATE,
                token_id=str(entity.id),
            )
            raise
        except OperationalError:
            logger.error(
                event=PasswordSetTokenErrorEvents.DB_UNAVAILABLE, op=Operation.UPDATE
            )
            raise
