from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.domain.project import Project, ProjectStatus, PublishingStatus
from src.repository.dutyy_repo import DutyRepo
from src.repository.project_repo import ProjectRepo
from tests.conftest import make_project

if TYPE_CHECKING:
    from src.domain.project import Project


@pytest.mark.integration
class TestProjectRepo:
    async def test_get_all_projects_success(self, session, project):
        repo = ProjectRepo(session)
        results: list[Project] = await repo.get_all()

        assert len(results) == 1
        assert isinstance(results[0], Project)
        assert results[0].id == project.id

    async def test_get_all_projects_returns_empty_list(self, session):
        repo = ProjectRepo(session)
        results: list[Project] = await repo.get_all()

        assert len(results) == 0

    async def test_delete_project_success(self, session, project):
        repo = ProjectRepo(session)

        existing: list[Project] = await repo.get_all()
        assert len(existing) == 1
        assert isinstance(existing[0], Project)

        await repo.delete(project)

        results: list[Project] = await repo.get_all()

        assert len(results) == 0

    async def test_add_project_success(self, session, user):
        repo = ProjectRepo(session)

        project = make_project(user.id)

        empty: list[Project] = await repo.get_all()

        assert len(empty) == 0

        await repo.add(project)

        results: list[Project] = await repo.get_all()

        assert len(results) == 1
        assert isinstance(results[0], Project)
        assert results[0].id == project.id
        assert results[0].owner_id == user.id

    async def test_update_project_success(self, session, project):
        repo = ProjectRepo(session)

        assert project.status == ProjectStatus.NEW

        project.update_status(ProjectStatus.IN_PROGRESS)

        await repo.update(project)

        result: Project | None = await repo.get_by_id(project.id)

        assert result is not None
        assert isinstance(result, Project)
        assert project.status == ProjectStatus.IN_PROGRESS

    async def test_get_by_id_success(self, session, project):
        repo = ProjectRepo(session)
        result: Project | None = await repo.get_by_id(project.id)

        assert result is not None
        assert isinstance(result, Project)
        assert result.status == project.status

    async def test_get_by_id_with_dutyys_loads_collection(
        self, session, project, dutyy
    ):
        session.expunge_all()
        repo = ProjectRepo(session)

        result = await repo.get_by_id_with_dutyys(project.id)

        assert result is not None
        assert [item.id for item in result.dutyys] == [dutyy.id]

    async def test_removing_loaded_dutyy_deletes_orphan(self, session, project, dutyy):
        session.expunge_all()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id_with_dutyys(project.id)
        assert loaded is not None

        loaded.delete_dutyy(dutyy.id)
        await repo.update(loaded)

        assert await DutyRepo(session).get_by_id(dutyy.id) is None

    async def test_get_by_id_resturns_none(self, session, user):
        repo = ProjectRepo(session)

        project: Project = make_project(user.id)

        result: Project | None = await repo.get_by_id(project.id)

        assert result is None

    async def test_search_by_name_returns_non_empty_list(self, session, project, user):
        repo = ProjectRepo(session)

        second_project = make_project(name="Second Test ", owner_id=user.id)

        await repo.add(second_project)

        results: list[Project] = await repo.search_by_name("Test", owner_id=user.id)

        assert isinstance(results, list)
        assert isinstance(results[0], Project)
        assert len(results) == 2

    async def test_search_by_name_returns_empty_list(self, session, user):
        repo = ProjectRepo(session)

        results: list[Project] = await repo.search_by_name("Test", owner_id=user.id)

        assert len(results) == 0

    async def test_get_by_owner_id_returns_non_empty_list(self, session, project, user):
        repo = ProjectRepo(session)

        results: list[Project] = await repo.get_by_owner_id(user.id)

        assert len(results) == 1
        assert isinstance(results[0], Project)

    async def test_get_by_owner_id_returns_empty_list(self, session, user):
        repo = ProjectRepo(session)

        results: list[Project] = await repo.get_by_owner_id(user.id)

        assert len(results) == 0

    async def test_get_projects_by_user_id_success(self, session, project, user):
        repo = ProjectRepo(session)
        results: list[Project] = await repo.get_projects_by_user_id(user.id)

        assert len(results) == 1
        assert isinstance(results[0], Project)

    async def test_get_projects_by_user_id_returns_empty_list(self, session, user):
        repo = ProjectRepo(session)
        results: list[Project] = await repo.get_projects_by_user_id(user.id)

        assert isinstance(results, list)
        assert len(results) == 0

    async def test_add_project_persists_draft_defaults(self, session, user):
        repo = ProjectRepo(session)

        project = make_project(user.id)
        await repo.add(project)

        result: Project | None = await repo.get_by_id(project.id)

        assert result is not None
        assert result.publishing_status == PublishingStatus.DRAFT
        assert result.published_date is None

    async def test_update_project_publishes(self, session, project, dutyy):
        session.expunge_all()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id_with_dutyys(project.id)
        assert loaded is not None

        assert loaded.publishing_status == PublishingStatus.DRAFT

        loaded.publish()

        await repo.update(loaded)

        result: Project | None = await repo.get_by_id(project.id)

        assert result is not None
        assert result.publishing_status == PublishingStatus.PUBLISHED
        assert result.published_date == loaded.published_date

    async def test_update_project_unpublish_retains_date(self, session, project, dutyy):
        session.expunge_all()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id_with_dutyys(project.id)
        assert loaded is not None

        loaded.publish()
        await repo.update(loaded)
        published_date = loaded.published_date

        loaded.unpublish()
        await repo.update(loaded)

        result: Project | None = await repo.get_by_id(project.id)

        assert result is not None
        assert result.publishing_status == PublishingStatus.DRAFT
        assert result.published_date == published_date

    async def test_search_by_name_owner_isolation(self, session, project, user):
        from src.repository.user_repo import UserRepo
        from tests.conftest import make_user

        repo = ProjectRepo(session)

        other_user = make_user(
            first_name="Jane", last_name="Doe", email="jane@example.com"
        )
        await UserRepo(session).add(other_user)

        other_project = make_project(other_user.id, name="Test Other")
        await repo.add(other_project)

        results: list[Project] = await repo.search_by_name("Test", owner_id=user.id)

        assert len(results) == 1
        assert results[0].id == project.id
