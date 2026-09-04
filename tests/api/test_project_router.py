from collections.abc import Iterator
from uuid import uuid7

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_current_user, get_project_service
from src.domain.dutyy import DutyyStatus
from src.domain.project import ProjectStatus, PublishingStatus
from src.main import create_app
from src.repository.dutyy_repo import DutyRepo
from src.repository.project_repo import ProjectRepo
from tests.conftest import make_project_service, make_user


@pytest.fixture
def project_service(session, event_bus):
    return make_project_service(session, event_bus)


@pytest.fixture
def app(project_service) -> Iterator[FastAPI]:
    app = create_app()
    app.dependency_overrides[get_project_service] = lambda: project_service
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def as_user(app, user) -> FastAPI:
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


class TestProjectRouter:
    _PROJECTS_URL = "/dutyy/api/v1/projects"

    async def test_create_project_returns_201(self, client, as_user, user):
        response = await client.post(self._PROJECTS_URL, json={"name": " New Project "})

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "new project"
        assert body["owner_id"] == str(user.id)
        assert body["publishing_status"] == PublishingStatus.DRAFT
        assert body["dutyys"] == []

    async def test_list_projects_includes_dutyys(
        self, client, as_user, project, project_service, db_roundtrip
    ):
        await project_service.add_dutyy(
            dutyy_title="First Dutyy",
            project_id=project.id,
            owner_id=project.owner_id,
        )
        await db_roundtrip()

        response = await client.get(self._PROJECTS_URL)

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["id"] == str(project.id)
        assert body[0]["dutyys"][0]["title"] == "first dutyy"

    async def test_get_project_returns_owner_project(self, client, as_user, project):
        response = await client.get(f"{self._PROJECTS_URL}/{project.id}")

        assert response.status_code == 200
        assert response.json()["id"] == str(project.id)

    async def test_patch_project_updates_all_fields(self, client, as_user, project):
        response = await client.patch(
            f"{self._PROJECTS_URL}/{project.id}",
            json={"name": " Updated Project ", "status": ProjectStatus.IN_PROGRESS},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "updated project"
        assert body["status"] == ProjectStatus.IN_PROGRESS

    async def test_publish_project_returns_empty_204(
        self, client, as_user, project, project_service, db_roundtrip, session
    ):
        await project_service.add_dutyy(
            dutyy_title="Publish Me",
            project_id=project.id,
            owner_id=project.owner_id,
        )

        response = await client.post(f"{self._PROJECTS_URL}/{project.id}/publish")

        assert response.status_code == 204
        assert response.content == b""
        await db_roundtrip()
        persisted = await ProjectRepo(session).get_by_id(project.id, project.owner_id)
        assert persisted is not None
        assert persisted.publishing_status == PublishingStatus.PUBLISHED

    async def test_unpublish_project_returns_updated_project(
        self, client, as_user, project, project_service
    ):
        await project_service.add_dutyy(
            dutyy_title="Publish Me",
            project_id=project.id,
            owner_id=project.owner_id,
        )
        await project_service.publish_project(project.id, project.owner_id)

        response = await client.post(f"{self._PROJECTS_URL}/{project.id}/unpublish")

        assert response.status_code == 200
        assert response.json()["publishing_status"] == PublishingStatus.DRAFT

    async def test_add_dutyy_returns_201(self, client, as_user, project):
        response = await client.post(
            f"{self._PROJECTS_URL}/{project.id}/dutyys",
            json={"title": " New Dutyy ", "details": " details "},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "new dutyy"
        assert body["details"] == "details"
        assert body["project_id"] == str(project.id)

    async def test_patch_dutyy_updates_all_fields(
        self, client, as_user, project, project_service
    ):
        dutyy = await project_service.add_dutyy(
            dutyy_title="Original",
            project_id=project.id,
            owner_id=project.owner_id,
        )

        response = await client.patch(
            f"/dutyy/api/v1/dutyys/{dutyy.id}",
            json={
                "title": " Updated ",
                "details": " new details ",
                "status": DutyyStatus.COMPLETE,
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "updated"
        assert body["details"] == "new details"
        assert body["status"] == DutyyStatus.COMPLETE
        assert body["completed_date"] is not None

    async def test_delete_dutyy_returns_empty_204_and_deletes_it(
        self, client, as_user, project, project_service, db_roundtrip, session
    ):
        dutyy = await project_service.add_dutyy(
            dutyy_title="Delete Me",
            project_id=project.id,
            owner_id=project.owner_id,
        )

        response = await client.delete(
            f"{self._PROJECTS_URL}/{project.id}/dutyys/{dutyy.id}"
        )

        assert response.status_code == 204
        assert response.content == b""
        await db_roundtrip()
        assert await DutyRepo(session).get_by_id(dutyy.id) is None

    async def test_project_routes_require_authentication(self, client):
        response = await client.get(self._PROJECTS_URL)

        assert response.status_code == 401

    async def test_cross_owner_project_is_not_found(self, client, app, project):
        other_user = make_user(email="other@example.com")
        app.dependency_overrides[get_current_user] = lambda: other_user

        response = await client.get(f"{self._PROJECTS_URL}/{project.id}")

        assert response.status_code == 404
        assert response.json() == {"detail": f"Project with id {project.id} not found"}

    @pytest.mark.parametrize(
        ("path", "payload"),
        [
            ("/dutyy/api/v1/projects/{id}", {}),
            ("/dutyy/api/v1/dutyys/{id}", {}),
        ],
    )
    async def test_empty_patch_returns_400(
        self, client, as_user, project, project_service, path, payload
    ):
        dutyy = await project_service.add_dutyy(
            dutyy_title="Existing",
            project_id=project.id,
            owner_id=project.owner_id,
        )
        resource_id = project.id if "/projects/" in path else dutyy.id

        response = await client.patch(path.format(id=resource_id), json=payload)

        assert response.status_code == 400
        assert response.json() == {"detail": "no fields provided to update"}

    async def test_unknown_dutyy_returns_404(self, client, as_user):
        dutyy_id = uuid7()

        response = await client.patch(
            f"/dutyy/api/v1/dutyys/{dutyy_id}", json={"title": "Updated"}
        )

        assert response.status_code == 404
        assert response.json() == {"detail": f"Dutyy with id {dutyy_id} not found"}

    async def test_delete_unassigned_dutyy_returns_404(self, client, as_user, project):
        dutyy_id = uuid7()

        response = await client.delete(
            f"{self._PROJECTS_URL}/{project.id}/dutyys/{dutyy_id}"
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": f"Dutyy with id {dutyy_id} is not assigned to project"
        }

    async def test_add_dutyy_to_published_project_returns_422(
        self, client, as_user, project, project_service
    ):
        await project_service.add_dutyy(
            dutyy_title="Existing",
            project_id=project.id,
            owner_id=project.owner_id,
        )
        await project_service.publish_project(project.id, project.owner_id)

        response = await client.post(
            f"{self._PROJECTS_URL}/{project.id}/dutyys",
            json={"title": "Rejected"},
        )

        assert response.status_code == 422
        assert response.json() == {"errors": ["project_not_in_draft_mode"]}
