from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING

from src.repository.dutyy_repo import DutyRepo
from src.repository.project_repo import ProjectRepo
from src.repository.user_repo import UserRepo
from src.repository.api_repo import APIRepo
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

logger = get_logger(__name__)


class AbstractUnitOfWork(ABC):
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        pass

    async def __aexit__(self, exc_type):
        pass


class UnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def __aenter__(self):
        self._session: AsyncSession = self._session_factory()
        self.dutyy = DutyRepo(self._session)
        self.project = ProjectRepo(self._session)
        self.user = UserRepo(self._session)
        self.api = APIRepo(self._session)
        return self

    async def __aexit__(self, exc_type, *_) -> None:
        if exc_type:
            logger.warning(event="uow_rollback", reason=str(exc_type))
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        logger.debug(event="uow_commit")
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
