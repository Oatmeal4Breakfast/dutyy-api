from __future__ import annotations
import pytest
from typing import TYPE_CHECKING


from src.repository.dutyy_repo import DutyRepo
from src.domain.enums import DutyyStatus
from tests.conftest import make_dutyy, make_project

if TYPE_CHECKING:
    from src.domain.dutyy import Dutyy


@pytest.mark.integration
class TestDutyyRepo:
    async def test_get_all(self, session, dutyy):
        repo = DutyRepo(session)
        result: list[Dutyy] = await repo.get_all()

        assert len(result) == 1
        assert result[0].id == dutyy.id

    async def test_get_all_returns_empty_list(self, session):
        repo = DutyRepo(session)

        result: list[Dutyy] = await repo.get_all()

        assert len(result) == 0

    async def test_delete_dutyy_success(self, session, dutyy):
        repo = DutyRepo(session)

        get_all: list[Dutyy] = await repo.get_all()
        assert len(get_all) == 1

        await repo.delete(dutyy)

        result: list[Dutyy] = await repo.get_all()
        assert len(result) == 0

    async def test_add_dutyy_sucess(self, session, project):
        repo = DutyRepo(session)

        dutyy: Dutyy = make_dutyy(project.id)

        empty: list[Dutyy] = await repo.get_all()
        assert len(empty) == 0

        await repo.add(dutyy)

        result: Dutyy | None = await repo.get_by_id(dutyy.id)
        assert result is not None

    async def test_update_dutyy_success(self, session, dutyy):
        repo = DutyRepo(session)

        assert dutyy.status == DutyyStatus.NEW

        dutyy.update_status(DutyyStatus.IN_PROGRESS)

        await repo.update(dutyy)

        result: Dutyy | None = await repo.get_by_id(dutyy.id)

        assert result is not None
        assert result.status == DutyyStatus.IN_PROGRESS

    async def test_get_by_id_success(self, session, dutyy):
        repo = DutyRepo(session)

        result: Dutyy | None = await repo.get_by_id(dutyy.id)
        assert result is not None

    async def test_get_by_project_id_success(self, session, dutyy, project):
        repo = DutyRepo(session)

        result: list[Dutyy] = await repo.get_by_project_id(project.id)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].id == dutyy.id
        assert result[0].project_id == project.id

    async def test_get_by_id_returns_empty_list(self, session, user):
        repo = DutyRepo(session)

        project = make_project(user.id)

        result: list[Dutyy] = await repo.get_by_project_id(project.id)

        assert isinstance(result, list)
        assert len(result) == 0

    async def test_search_by_name(self, session, dutyy, user):
        repo = DutyRepo(session)

        results: list[Dutyy] = await repo.search_by_name("test", user.id)

        assert isinstance(results, list)
        assert results[0].project_id == dutyy.project_id
