from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.db.uow import AbstractUnitOfWork
from src.domain.dutyy import Dutyy, DutyyStatus
from src.domain.project import Project, ProjectStatus
from src.logger import get_logger

if TYPE_CHECKING:
    from uuid import UUID


logger = get_logger(__name__)


class ProjectNotFoundError(Exception):
    def __init__(self, id: UUID) -> None:
        self.id = id
        super().__init__(f"Project with id {self.id} not found")


class DutyyNotFoundError(Exception):
    def __init__(self, id: UUID) -> None:
        self.id = id
        super().__init__(f"Dutyy with id {self.id} not found")


@dataclass(frozen=True)
class EditDutyyCommand:
    title: str | None = None
    details: str | None = None
    status: DutyyStatus | None = None


@dataclass(frozen=True)
class EditProjectCommand:
    name: str | None = None
    status: ProjectStatus | None = None


class ProjectService:
    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
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

    async def publish_project(self, project_id: UUID, owner_id: UUID) -> None:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                raise ProjectNotFoundError(project_id)

            project.publish()

            await uow.project.update(project)
            await uow.commit()
            return

    async def add_dutyy(
        self,
        dutyy_title: str,
        project_id: UUID,
        owner_id: UUID,
        details: str | None = None,
    ) -> Dutyy:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(
                    event="project_not_found",
                    project_id=str(project_id),
                )
                raise ProjectNotFoundError(project_id)

            dutyy = Dutyy(title=dutyy_title, project_id=project_id, details=details)

            project.add_dutyy(dutyy)

            await uow.project.update(project)
            await uow.commit()

            return dutyy

    async def remove_dutyy(
        self, dutyy_id: UUID, project_id: UUID, owner_id: UUID
    ) -> None:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                raise ProjectNotFoundError(project_id)

            project.delete_dutyy(dutyy_id)
            await uow.project.update(project)
            await uow.commit()

    async def edit_dutyy(
        self, dutyy_id: UUID, owner_id: UUID, updates: EditDutyyCommand
    ) -> Dutyy:
        async with self._uow_factory() as uow:
            dutyy: Dutyy | None = await uow.dutyy.get_by_id_with_owner(
                dutyy_id=dutyy_id, owner_id=owner_id
            )

            if dutyy is None:
                logger.warning(event="dutyy_not_found", dutyy_id=str(dutyy_id))
                raise DutyyNotFoundError(dutyy_id)

            if (
                updates.title is None
                and updates.details is None
                and updates.status is None
            ):
                return dutyy

            if updates.title is not None:
                dutyy.update_title(updates.title)

            if updates.details is not None:
                dutyy.update_details(updates.details)

            if updates.status is not None:
                dutyy.update_status(updates.status)

            await uow.dutyy.update(dutyy)
            await uow.commit()

            return dutyy

    async def edit_project(
        self, project_id: UUID, owner_id: UUID, updates: EditProjectCommand
    ) -> Project:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                raise ProjectNotFoundError(project_id)

            if updates.name is None and updates.status is None:
                return project

            if updates.name is not None:
                project.update_name(updates.name)

            if updates.status is not None:
                project.update_status(updates.status)

            await uow.project.update(project)
            await uow.commit()

            return project

    async def unpublish_project(self, project_id: UUID, owner_id: UUID) -> Project:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                raise ProjectNotFoundError(project_id)

            project.unpublish()

            await uow.project.update(project)
            await uow.commit()

            return project

    async def get_project(self, project_id: UUID, owner_id: UUID) -> Project:
        async with self._uow_factory() as uow:
            project: Project | None = await uow.project.get_by_id(
                project_id=project_id, owner_id=owner_id
            )

            if project is None:
                logger.warning(event="project_not_found", project_id=str(project_id))
                raise ProjectNotFoundError(project_id)
            return project

    async def list_projects(self, owner_id: UUID) -> list[Project]:
        async with self._uow_factory() as uow:
            return await uow.project.get_by_owner_id(owner_id=owner_id)
