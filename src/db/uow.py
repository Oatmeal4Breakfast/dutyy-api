from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.bus.bus import EventBus
from src.logger import get_logger
from src.repository.api_repo import APIRepo
from src.repository.device_auth_repo import DeviceAuthRepo
from src.repository.dutyy_repo import DutyRepo
from src.repository.health_repo import HealthRepo
from src.repository.project_repo import ProjectRepo
from src.repository.token_repo import PasswordSetTokenRepo
from src.repository.user_repo import UserRepo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.domain.events import Event

logger = get_logger(__name__)


class AbstractUnitOfWork(ABC):
    bus: EventBus
    dutyy: DutyRepo
    project: ProjectRepo
    user: UserRepo
    api: APIRepo
    health: HealthRepo
    token: PasswordSetTokenRepo
    device_auth: DeviceAuthRepo
    _session: AsyncSession

    @abstractmethod
    async def __aenter__(self) -> AbstractUnitOfWork: ...

    @abstractmethod
    async def __aexit__(self, exc_type, *_) -> None: ...

    async def publish_events(self) -> None:
        registered_repos: list = [self.dutyy, self.project, self.user]
        events: list[Event] = []

        for repo in registered_repos:
            for entity in repo.seen:
                for event in entity.events:
                    events.append(event)
                entity.events.clear()
            repo.seen.clear()

        tasks = [self.bus.publish(event) for event in events]
        await asyncio.gather(*tasks)

    async def commit(self) -> None:
        logger.debug(event="uow_commit")
        await self._session.commit()
        await self.publish_events()

    async def rollback(self) -> None:
        await self._session.rollback()


class UnitOfWork(AbstractUnitOfWork):
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus
    ):
        self._session_factory = session_factory
        self.bus = event_bus

    async def __aenter__(self) -> UnitOfWork:
        self._session = self._session_factory()
        self.dutyy = DutyRepo(self._session)
        self.project = ProjectRepo(self._session)
        self.user = UserRepo(self._session)
        self.api = APIRepo(self._session)
        self.health = HealthRepo(self._session)
        self.token = PasswordSetTokenRepo(self._session)
        self.device_auth = DeviceAuthRepo(self._session)
        return self

    async def __aexit__(self, exc_type, *_) -> None:
        if exc_type:
            logger.warning(event="uow_rollback", reason=str(exc_type))
            await self.rollback()
        await self._session.close()
