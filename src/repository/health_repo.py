from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger(__name__)


class HealthRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session: AsyncSession = session

    async def ping(self) -> None:
        try:
            await self._session.execute(text("SELECT 1"))
        except OperationalError as e:
            logger.error(event="database_unavailable", err=str(e))
            raise
