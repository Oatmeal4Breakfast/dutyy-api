from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import CursorResult, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from src.db.orm import device_auth_code_table
from src.domain.device_auth import DeviceCode, DeviceCodeDict, DeviceCodeStatus
from src.logger import get_logger
from src.repository.abstract_repo import Operation, RepoError

if TYPE_CHECKING:
    from sqlalchemy import Result, RowMapping, Select, Update
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class DeviceAuthRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def get_code_by_user_code(self, user_code: str) -> DeviceCode | None:
        stmt: Select = select(device_auth_code_table).where(
            device_auth_code_table.c.user_code == user_code
        )

        try:
            result: Result = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise
        row: RowMapping | None = result.mappings().one_or_none()
        return DeviceCode(**row) if row is not None else None

    async def get_code_by_hash(self, hash: str) -> DeviceCode | None:
        stmt: Select = select(device_auth_code_table).where(
            device_auth_code_table.c.hashed_device_code == hash
        )

        try:
            result: Result = await self._session.execute(stmt)
        except OperationalError:
            logger.error(event=RepoError.DB_UNAVAILABLE, op=Operation.GET)
            raise

        row: RowMapping | None = result.mappings().one_or_none()

        return DeviceCode(**row) if row is not None else None

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
        data: DeviceCodeDict = entity.to_dict()
        stmt: Update = (
            update(device_auth_code_table)
            .where(
                device_auth_code_table.c.hashed_device_code == entity.hashed_device_code
            )
            .values(**data)
        )

        try:
            await self._session.execute(stmt)
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
        updates: dict[str, DeviceCodeStatus] = {"status": DeviceCodeStatus.CONSUMED}
        stmt: Update = (
            update(device_auth_code_table)
            .where(
                device_auth_code_table.c.hashed_device_code == hashed_device_code,
                device_auth_code_table.c.status == DeviceCodeStatus.APPROVED,
                device_auth_code_table.c.expires_at > func.now(),
            )
            .values(**updates)
            .returning(device_auth_code_table)
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

        row: RowMapping | None = result.mappings().one_or_none()
        return DeviceCode(**row) if row is not None else None

    async def purge(self) -> int:
        stmt = delete(device_auth_code_table).where(
            or_(
                device_auth_code_table.c.status == DeviceCodeStatus.CONSUMED,
                device_auth_code_table.c.expires_at < func.now(),
            )
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
