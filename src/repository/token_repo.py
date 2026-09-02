from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import password_set_tokens_table
from src.domain.token import PasswordSetToken
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, RowMapping, Select, Update
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PasswordSetTokenRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entity: PasswordSetToken) -> None:
        self._session.add(entity)
        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                token_id=str(entity.id),
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def get_by_hash(self, token_hash: str) -> PasswordSetToken | None:
        stmt: Select[Any] = select(password_set_tokens_table).where(
            password_set_tokens_table.c.token_hash == token_hash
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return PasswordSetToken(**row) if row is not None else None

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
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                token_id=str(entity.id),
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def get_active_by_user_id(self, user_id: UUID) -> list[PasswordSetToken]:
        stmt: Select[Any] = (
            select(password_set_tokens_table)
            .where(password_set_tokens_table.c.user_id == user_id)
            .where(password_set_tokens_table.c.used_at.is_(None))
            .where(password_set_tokens_table.c.expires_at > func.now())
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        rows: Sequence[RowMapping] = result.mappings().fetchall()

        return [PasswordSetToken(**row) for row in rows]
