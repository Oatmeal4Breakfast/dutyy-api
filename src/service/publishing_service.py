from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from src.db.uow import AbstractUnitOfWork
from src.domain.dutyy import Dutyy
from src.domain.project import Project
from src.logger import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.bus.bus import EventBus

logger = get_logger(__name__)


class PublishingService:
    def __init__(
        self,
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
    ) -> None:
        self._uow_factory: Callable = uow_factory

    async def create_project_draft(
        self, project_name: str, owner_id: UUID, dutyys: list[Dutyy] | None = None
    ) -> Project:
        project = Project(
            name=project_name,
            owner_id=owner_id,
            dutyys=dutyys if dutyys is not None else [],
        )
        async with self._uow_factory() as uow:
            await uow.project.add(project)
            await uow.commit()
            logger.info(
                event="new_project_created",
                project_id=str(project.id),
                owner_id=str(owner_id),
            )
        return project

    async def publish_project(self, project_id: UUID) -> None:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(project_id=project_id)

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                return

            if len(project.dutyys) <= 0:
                logger.warning(
                    event="project_has no dutyys",
                    project_id=str(project.id),
                )
                return

            project.publish()
