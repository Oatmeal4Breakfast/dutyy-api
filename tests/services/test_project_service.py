from unittest.mock import AsyncMock
from uuid import uuid7

import pytest

from src.domain.events import DutyyRemoved
from src.domain.exceptions import DutyyNotAssignedError
from src.repository.dutyy_repo import DutyRepo
from src.service.project_service import ProjectNotFound
from tests.conftest import make_project_service


@pytest.mark.integration
class TestProjectService:
    async def test_remove_dutyy_deletes_it_and_fires_event(
        self, session, event_bus, project, dutyy
    ):
        handler = AsyncMock()
        event_bus.subscribe(DutyyRemoved, handler)
        session.expunge_all()
        service = make_project_service(session, event_bus)

        await service.remove_dutyy(dutyy_id=dutyy.id, project_id=project.id)
        await event_bus.drain()

        assert await DutyRepo(session).get_by_id(dutyy.id) is None
        handler.assert_awaited_once()
        event = handler.await_args.args[0]
        assert event.dutyy_id == dutyy.id
        assert event.project_id == project.id

    async def test_remove_dutyy_rejects_unknown_project(self, session, event_bus):
        service = make_project_service(session, event_bus)

        with pytest.raises(ProjectNotFound):
            await service.remove_dutyy(dutyy_id=uuid7(), project_id=uuid7())

    async def test_remove_dutyy_rejects_unassigned_id(
        self, session, event_bus, project
    ):
        session.expunge_all()
        service = make_project_service(session, event_bus)

        with pytest.raises(DutyyNotAssignedError):
            await service.remove_dutyy(dutyy_id=uuid7(), project_id=project.id)
