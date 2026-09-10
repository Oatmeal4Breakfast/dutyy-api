from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence, cast

from sqlalchemy import CursorResult, delete, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError

from src.domain.session import WebSession
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError, assert_managed

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy import Result, Select
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class WebSessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_token_hash(self, token_hash: str) -> WebSession | None:
        stmt: Select[tuple[WebSession]] = select(WebSession).where(
            WebSession.token_hash == token_hash
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()

    async def add(self, entity: WebSession) -> None:
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

    async def update(self, entity: WebSession) -> None:
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

    async def revoke(self, user_id: UUID, token_hash: str) -> WebSession | None:
        stmt: Select[tuple[WebSession]] = (
            select(WebSession)
            .where(
                WebSession.user_id == user_id,
                WebSession.token_hash == token_hash,
            )
            .with_for_update()
        )

        try:
            result: Result[tuple[WebSession]] = await self._session.execute(stmt)
            session: WebSession | None = result.scalars().one_or_none()

            if session is None:
                return

            session.revoke()

            await self._session.flush()
            return session
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        stmt: Select[tuple[WebSession]] = (
            select(WebSession)
            .where(WebSession.user_id == user_id, WebSession.revoked_at.is_(None))
            .with_for_update()
        )

        try:
            results: Result[tuple[WebSession]] = await self._session.execute(stmt)

            sessions: Sequence[WebSession] = results.scalars().all()

            for s in sessions:
                s.revoke()

            await self._session.flush()
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def purge(self) -> int:
        stmt = (
            delete(WebSession)
            .where(
                or_(
                    WebSession.revoked_at.is_not(None),
                    WebSession.idle_expires_at < func.now(),
                    WebSession.absolute_expires_at < func.now(),
                )
            )
            .execution_options(synchronize_session=False)
        )

        try:
            result: Result[Any] = await self._session.execute(stmt)
            result = cast(CursorResult, result)
            await self._session.flush()
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

        logger.info(event="web_session_purged", count=result.rowcount)
        return result.rowcount
