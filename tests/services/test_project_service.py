from unittest.mock import AsyncMock
from uuid import uuid7

import pytest

from src.domain.dutyy import DutyyStatus
from src.domain.events import (
    DutyyAdded,
    DutyyCompleted,
    DutyyRemoved,
    ProjectCompleted,
    ProjectPublished,
)
from src.domain.exceptions import DomainValidationError, DutyyNotAssignedError
from src.domain.project import ProjectStatus, PublishingStatus
from src.repository.dutyy_repo import DutyRepo
from src.repository.project_repo import ProjectRepo
from src.service.project_service import (
    DutyyNotFoundError,
    EditDutyyCommand,
    EditProjectCommand,
    ProjectNotFoundError,
)
from tests.conftest import make_project_service


@pytest.mark.integration
class TestProjectService:
    async def test_create_project_draft_persists_project(
        self, session, event_bus, user, db_roundtrip
    ):
        service = make_project_service(session, event_bus)

        created = await service.create_project_draft(" New Project ", user.id)

        await db_roundtrip()
        persisted = await ProjectRepo(session).get_by_id(created.id, user.id)

        assert persisted is not None
        assert persisted.name == "new project"
        assert persisted.owner_id == user.id
        assert persisted.publishing_status == PublishingStatus.DRAFT

    async def test_publish_project_persists_status_and_fires_event(
        self, session, event_bus, project, dutyy, db_roundtrip
    ):
        handler = AsyncMock()
        event_bus.subscribe(ProjectPublished, handler)
        await db_roundtrip()
        service = make_project_service(session, event_bus)

        await service.publish_project(project.id, project.owner_id)
        await event_bus.drain()

        await db_roundtrip()
        persisted = await ProjectRepo(session).get_by_id(project.id, project.owner_id)
        assert persisted is not None
        assert persisted.publishing_status == PublishingStatus.PUBLISHED
        assert persisted.published_date is not None
        handler.assert_awaited_once()

    async def test_publish_project_rejects_project_without_dutyys(
        self, session, event_bus, project, db_roundtrip
    ):
        await db_roundtrip()
        service = make_project_service(session, event_bus)

        with pytest.raises(DomainValidationError):
            await service.publish_project(project.id, project.owner_id)

    async def test_publish_project_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFoundError):
            await service.publish_project(uuid7(), uuid7())

    async def test_add_dutyy_persists_it_and_fires_event(
        self, session, event_bus, project, db_roundtrip
    ):
        handler = AsyncMock()
        event_bus.subscribe(DutyyAdded, handler)
        service = make_project_service(session, event_bus)

        created = await service.add_dutyy(
            dutyy_title=" New Dutyy ",
            project_id=project.id,
            owner_id=project.owner_id,
            details=" details ",
        )
        await event_bus.drain()

        await db_roundtrip()
        persisted = await DutyRepo(session).get_by_id(created.id)
        assert persisted is not None
        assert persisted.title == "new dutyy"
        assert persisted.details == "details"
        assert persisted.project_id == project.id
        handler.assert_awaited_once()

    async def test_add_dutyy_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFoundError):
            await service.add_dutyy("New Dutyy", uuid7(), uuid7())

    async def test_add_dutyy_rejects_published_project(
        self, session, event_bus, project, db_roundtrip
    ):
        service = make_project_service(session, event_bus)

        await service.add_dutyy(
            dutyy_title="old_dutyy", project_id=project.id, owner_id=project.owner_id
        )

        await service.publish_project(project_id=project.id, owner_id=project.owner_id)

        with pytest.raises(DomainValidationError) as exec_info:
            await service.add_dutyy(
                dutyy_title="new_dutyy",
                project_id=project.id,
                owner_id=project.owner_id,
            )

        assert exec_info.value.errors == ["project_not_in_draft_mode"]

    async def test_remove_dutyy_deletes_it_and_fires_event(
        self, session, event_bus, project, dutyy, db_roundtrip
    ):
        handler = AsyncMock()
        event_bus.subscribe(DutyyRemoved, handler)
        await db_roundtrip()
        service = make_project_service(session, event_bus)

        await service.remove_dutyy(
            dutyy_id=dutyy.id, project_id=project.id, owner_id=project.owner_id
        )
        await event_bus.drain()

        await db_roundtrip()
        assert await DutyRepo(session).get_by_id(dutyy.id) is None
        handler.assert_awaited_once()
        event = handler.await_args.args[0]
        assert event.dutyy_id == dutyy.id
        assert event.project_id == project.id

    async def test_remove_dutyy_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFoundError):
            await service.remove_dutyy(
                dutyy_id=uuid7(), project_id=uuid7(), owner_id=uuid7()
            )

    async def test_remove_dutyy_rejects_unassigned_id(
        self, session, event_bus, project, db_roundtrip
    ):
        await db_roundtrip()
        service = make_project_service(session, event_bus)

        with pytest.raises(DutyyNotAssignedError):
            await service.remove_dutyy(
                dutyy_id=uuid7(), project_id=project.id, owner_id=project.owner_id
            )

    async def test_edit_dutyy_persists_all_changes_and_fires_completion_event(
        self, session, event_bus, user, dutyy, db_roundtrip
    ):
        handler = AsyncMock()
        event_bus.subscribe(DutyyCompleted, handler)
        service = make_project_service(session, event_bus)

        updated = await service.edit_dutyy(
            dutyy.id,
            user.id,
            EditDutyyCommand(
                title=" Updated Title ",
                details=" updated details ",
                status=DutyyStatus.COMPLETE,
            ),
        )
        await event_bus.drain()

        await db_roundtrip()
        persisted = await DutyRepo(session).get_by_id(dutyy.id)
        assert persisted is not None
        assert updated.title == persisted.title == "updated title"
        assert updated.details == persisted.details == "updated details"
        assert persisted.status == DutyyStatus.COMPLETE
        assert persisted.completed_date is not None
        handler.assert_awaited_once()

    async def test_edit_dutyy_empty_command_is_noop(
        self, session, event_bus, user, dutyy
    ):
        service = make_project_service(session, event_bus)

        updated = await service.edit_dutyy(dutyy.id, user.id, EditDutyyCommand())

        assert updated.modified_date is None

    async def test_edit_dutyy_validates_empty_title(
        self, session, event_bus, user, dutyy
    ):
        service = make_project_service(session, event_bus)

        with pytest.raises(DomainValidationError):
            await service.edit_dutyy(dutyy.id, user.id, EditDutyyCommand(title=""))

    async def test_edit_dutyy_rejects_unknown_dutyy(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(DutyyNotFoundError):
            await service.edit_dutyy(
                uuid7(), uuid7(), EditDutyyCommand(title="Updated")
            )

    async def test_edit_project_persists_all_changes_and_fires_completion_event(
        self, session, event_bus, project, db_roundtrip
    ):
        handler = AsyncMock()
        event_bus.subscribe(ProjectCompleted, handler)
        service = make_project_service(session, event_bus)

        updated = await service.edit_project(
            project.id,
            project.owner_id,
            EditProjectCommand(name=" Updated Project ", status=ProjectStatus.COMPLETE),
        )
        await event_bus.drain()

        await db_roundtrip()
        persisted = await ProjectRepo(session).get_by_id(project.id, updated.owner_id)
        assert persisted is not None
        assert updated.name == persisted.name == "updated project"
        assert persisted.status == ProjectStatus.COMPLETE
        assert persisted.completed_date is not None
        handler.assert_awaited_once()

    async def test_edit_project_empty_command_is_noop(
        self, session, event_bus, project
    ):
        service = make_project_service(session, event_bus)

        updated = await service.edit_project(
            project.id, project.owner_id, EditProjectCommand()
        )

        assert updated.modified_date is None

    async def test_edit_project_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFoundError):
            await service.edit_project(
                uuid7(), uuid7(), EditProjectCommand(name="Updated")
            )

    async def test_unpublish_project_persists_draft_status(
        self, session, event_bus, project, dutyy, db_roundtrip
    ):
        await db_roundtrip()
        service = make_project_service(session, event_bus)
        await service.publish_project(project.id, project.owner_id)

        updated = await service.unpublish_project(project.id, project.owner_id)

        await db_roundtrip()
        persisted = await ProjectRepo(session).get_by_id(project.id, project.owner_id)
        assert persisted is not None
        assert updated.publishing_status == PublishingStatus.DRAFT
        assert persisted.publishing_status == PublishingStatus.DRAFT
        assert persisted.published_date is not None

    async def test_unpublish_project_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFoundError):
            await service.unpublish_project(uuid7(), uuid7())
