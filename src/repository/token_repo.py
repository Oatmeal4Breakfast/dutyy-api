from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.domain.token import PasswordSetToken
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError, assert_managed

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, Select
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
        stmt: Select[tuple[PasswordSetToken]] = select(PasswordSetToken).where(
            PasswordSetToken.token_hash == token_hash
        )

        try:
            result: Result[tuple[PasswordSetToken]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()

    async def update(self, entity: PasswordSetToken) -> None:
        assert_managed(self._session, entity)

        try:
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
        stmt: Select[tuple[PasswordSetToken]] = (
            select(PasswordSetToken)
            .where(PasswordSetToken.user_id == user_id)
            .where(PasswordSetToken.used_at.is_(None))
            .where(PasswordSetToken.expires_at > func.now())
        )

        try:
            result: Result[tuple[PasswordSetToken]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        tokens: Sequence[PasswordSetToken] = result.scalars().all()

        return list(tokens)
