from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import CursorResult, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import device_auth_code_table
from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError, assert_managed

if TYPE_CHECKING:
    from sqlalchemy import Result, Select, Update
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DeviceAuthRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def get_code_by_user_code(self, user_code: str) -> DeviceCode | None:
        stmt: Select[tuple[DeviceCode]] = select(DeviceCode).where(
            device_auth_code_table.c.user_code == user_code
        )

        try:
            result: Result[tuple[DeviceCode]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()

    async def get_code_by_hash(self, hash: str) -> DeviceCode | None:
        stmt: Select[tuple[DeviceCode]] = select(DeviceCode).where(
            device_auth_code_table.c.hashed_device_code == hash
        )

        try:
            result: Result[tuple[DeviceCode]] = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        return result.scalars().one_or_none()

    async def add(self, entity: DeviceCode) -> None:
        self._session.add(entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.ADD,
                hashed_device_code=entity.hashed_device_code,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.ADD)
            raise

    async def update(self, entity: DeviceCode) -> None:
        assert_managed(self._session, entity)

        try:
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                hashed_device_code=entity.hashed_device_code,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

    async def consume(self, hashed_device_code: str) -> DeviceCode | None:
        """Deliberately a statement rather than load-then-mutate.

        This is a race-safe compare-and-set: the APPROVED/expiry check lives in the
        WHERE clause so two concurrent polls cannot both consume the code. Reading the
        row and mutating it would reintroduce that race.

        It is an ORM-enabled UPDATE (`update(DeviceCode)`, not `update(table)`) so that
        `synchronize_session="fetch"` refreshes any instance of this row already in the
        session. A Core UPDATE here would write behind the identity map and a later read
        in the same session would hand back the stale pre-consume status.
        """
        updates: dict[str, DeviceCodeStatus] = {"status": DeviceCodeStatus.CONSUMED}
        stmt: Update = (
            update(DeviceCode)
            .where(
                device_auth_code_table.c.hashed_device_code == hashed_device_code,
                device_auth_code_table.c.status == DeviceCodeStatus.APPROVED,
                device_auth_code_table.c.expires_at > func.now(),
            )
            .values(**updates)
            .returning(DeviceCode)
            .execution_options(synchronize_session="fetch")
        )

        try:
            result: Result = await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError:
            logger.error(
                event=RepoError.INTEGRITY_CONFLICT,
                op=Operation.UPDATE,
                hashed_device_code=hashed_device_code,
            )
            raise
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.UPDATE)
            raise

        return result.scalars().one_or_none()

    async def purge(self) -> int:
        stmt = (
            delete(device_auth_code_table)
            .where(
                or_(
                    device_auth_code_table.c.status == DeviceCodeStatus.CONSUMED,
                    device_auth_code_table.c.expires_at < func.now(),
                )
            )
            .execution_options(synchronize_session=False)
        )

        try:
            result: Result = await self._session.execute(stmt)
            result = cast(CursorResult, result)
            await self._session.flush()
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.DELETE)
            raise

        logger.info(event="device_codes_purged", count=result.rowcount)
        return result.rowcount
