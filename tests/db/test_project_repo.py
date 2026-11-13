from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid7

import pytest
from sqlalchemy import select, update

from src.db.orm import project_user_table
from src.domain.project import Project, ProjectStatus, PublishingStatus
from src.repository.abstract_repo import DetachedEntityError
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

    async def test_delete_project_success(self, session, project, db_roundtrip):
        repo = ProjectRepo(session)
        other_project = make_project(project.owner_id, name="Keep Me")
        await repo.add(other_project)

        deleted_id = await repo.delete_entity(project.id, project.owner_id)

        assert deleted_id == project.id
        await db_roundtrip()
        assert await repo.get_by_id(project.id, project.owner_id) is None
        assert (
            await repo.get_by_id(other_project.id, other_project.owner_id) is not None
        )

    async def test_delete_project_cascades_to_its_dutyys(
        self, session, project, dutyy, db_roundtrip
    ):
        """Statement-based deletion relies on the database FK cascade."""
        await db_roundtrip()
        repo = ProjectRepo(session)

        assert await repo.delete_entity(project.id, project.owner_id) == project.id

        await db_roundtrip()
        assert await repo.get_by_id(project.id, project.owner_id) is None
        assert await DutyRepo(session).get_by_id(dutyy.id) is None

    async def test_delete_project_cascades_to_memberships(self, session, project):
        repo = ProjectRepo(session)
        stmt = select(project_user_table).where(
            project_user_table.c.project_id == project.id
        )
        assert (await session.execute(stmt)).all()

        await repo.delete_entity(project.id, project.owner_id)

        assert (await session.execute(stmt)).all() == []

    async def test_delete_unknown_project_returns_none(self, session, project):
        repo = ProjectRepo(session)

        assert await repo.delete_entity(uuid7(), project.owner_id) is None
        assert await repo.get_by_id(project.id, project.owner_id) is not None

    async def test_delete_project_scopes_to_owner(
        self, session, project, dutyy, db_roundtrip
    ):
        repo = ProjectRepo(session)

        assert await repo.delete_entity(project.id, uuid7()) is None

        await db_roundtrip()
        assert await repo.get_by_id(project.id, project.owner_id) is not None
        assert await DutyRepo(session).get_by_id(dutyy.id) is not None

    async def test_delete_project_twice_returns_none(self, session, project):
        repo = ProjectRepo(session)

        assert await repo.delete_entity(project.id, project.owner_id) == project.id
        assert await repo.delete_entity(project.id, project.owner_id) is None

    async def test_delete_checks_current_owner_after_an_earlier_read(
        self, session, project, db_roundtrip
    ):
        repo = ProjectRepo(session)
        original_owner_id = project.owner_id
        new_owner_id = uuid7()
        assert await repo.get_by_id(project.id, original_owner_id) is not None
        await session.execute(
            update(Project)
            .where(Project.id == project.id)
            .values(owner_id=new_owner_id)
            .execution_options(synchronize_session=False)
        )

        assert await repo.delete_entity(project.id, original_owner_id) is None

        await db_roundtrip()
        assert await repo.get_by_id(project.id, new_owner_id) is not None

    async def test_add_project_success(self, session, user, db_roundtrip):
        repo = ProjectRepo(session)

        project = make_project(user.id)

        empty: list[Project] = await repo.get_all()

        assert len(empty) == 0

        await repo.add(project)

        await db_roundtrip()
        results: list[Project] = await repo.get_all()

        assert len(results) == 1
        assert isinstance(results[0], Project)
        assert results[0].id == project.id
        assert results[0].owner_id == user.id

    async def test_update_project_success(self, session, project, db_roundtrip):
        repo = ProjectRepo(session)

        assert project.status == ProjectStatus.NEW

        project.update_status(ProjectStatus.IN_PROGRESS)

        await repo.update(project)

        await db_roundtrip()
        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

        assert result is not None
        assert isinstance(result, Project)
        assert result.status == ProjectStatus.IN_PROGRESS

    async def test_update_rejects_an_entity_this_session_does_not_manage(
        self, session, project, db_roundtrip
    ):
        """A flush-based update() on a detached entity would silently be a no-op."""
        repo = ProjectRepo(session)
        await db_roundtrip()

        project.update_status(ProjectStatus.IN_PROGRESS)

        with pytest.raises(DetachedEntityError):
            await repo.update(project)

    async def test_get_by_id_success(self, session, project):
        repo = ProjectRepo(session)
        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

        assert result is not None
        assert isinstance(result, Project)
        assert result.status == project.status

    async def test_get_by_id_returns_the_identity_mapped_instance(
        self, session, project
    ):
        """Without an expunge, a read is served by the session's identity map.

        This is the intended behaviour -- one object per row per session -- and is
        exactly why read-back assertions need `db_roundtrip` to prove anything.
        """
        repo = ProjectRepo(session)

        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

        assert result is project

    async def test_get_by_id_after_roundtrip_hits_the_database(
        self, session, project, db_roundtrip
    ):
        repo = ProjectRepo(session)
        await db_roundtrip()

        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

        assert result is not None
        assert result is not project
        assert result.id == project.id
        assert result.name == project.name

    async def test_get_by_id_scopes_to_owner(self, session, project):
        repo = ProjectRepo(session)

        assert await repo.get_by_id(project.id, uuid7()) is None

    async def test_get_by_id_loads_the_dutyy_collection(
        self, session, project, dutyy, db_roundtrip
    ):
        await db_roundtrip()
        repo = ProjectRepo(session)

        result = await repo.get_by_id(project.id, project.owner_id)

        assert result is not None
        assert [item.id for item in result.dutyys] == [dutyy.id]

    async def test_removing_loaded_dutyy_deletes_orphan(
        self, session, project, dutyy, db_roundtrip
    ):
        await db_roundtrip()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id(project.id, project.owner_id)
        assert loaded is not None

        loaded.delete_dutyy(dutyy.id)
        await repo.update(loaded)

        await db_roundtrip()
        assert await DutyRepo(session).get_by_id(dutyy.id) is None

    async def test_get_by_id_resturns_none(self, session, user):
        repo = ProjectRepo(session)

        project: Project = make_project(user.id)

        result: Project | None = await repo.get_by_id(project.id, user.id)

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

    async def test_get_by_owner_id_returns_non_empty_list(
        self, session, project, dutyy, user, db_roundtrip
    ):
        await db_roundtrip()
        repo = ProjectRepo(session)

        results: list[Project] = await repo.get_by_owner_id(user.id)

        assert len(results) == 1
        assert isinstance(results[0], Project)
        assert [item.id for item in results[0].dutyys] == [dutyy.id]

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

    async def test_add_project_persists_draft_defaults(
        self, session, user, db_roundtrip
    ):
        repo = ProjectRepo(session)

        project = make_project(user.id)
        await repo.add(project)

        await db_roundtrip()
        result: Project | None = await repo.get_by_id(project.id, user.id)

        assert result is not None
        assert result.publishing_status == PublishingStatus.DRAFT
        assert result.published_date is None

    async def test_update_project_publishes(
        self, session, project, dutyy, db_roundtrip
    ):
        await db_roundtrip()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id(project.id, project.owner_id)
        assert loaded is not None

        assert loaded.publishing_status == PublishingStatus.DRAFT

        loaded.publish()

        await repo.update(loaded)

        published_date = loaded.published_date

        await db_roundtrip()
        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

        assert result is not None
        assert result.publishing_status == PublishingStatus.PUBLISHED
        assert result.published_date == published_date

    async def test_update_project_unpublish_retains_date(
        self, session, project, dutyy, db_roundtrip
    ):
        await db_roundtrip()
        repo = ProjectRepo(session)
        loaded = await repo.get_by_id(project.id, project.owner_id)
        assert loaded is not None

        loaded.publish()
        await repo.update(loaded)
        published_date = loaded.published_date

        loaded.unpublish()
        await repo.update(loaded)

        await db_roundtrip()
        result: Project | None = await repo.get_by_id(project.id, project.owner_id)

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
