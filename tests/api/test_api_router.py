import pytest
from datetime import timedelta

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.main import create_app
from src.api.deps import get_api_service, get_current_user
from src.domain.api import APIKeyStatus
from tests.conftest import make_api_service


@pytest.fixture
def app(session, event_bus) -> FastAPI:
    app = create_app()
    app.dependency_overrides[get_api_service] = lambda: make_api_service(
        session, event_bus
    )
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def as_user(app, user) -> FastAPI:
    """Opt-in: bypass real JWT auth and run every route as `user`."""
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestApiKeyRouter:
    _API_URL = "/dutyy/api/v1/api-keys"

    async def test_issue_new_key_returns_201(self, client, as_user):
        resp = await client.post(
            url=self._API_URL, json={"key_name": "cli_test", "ttl": "7d"}
        )

        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body["api-key"], str)
        assert body["api-key"]

    async def test_get_api_keys_success(
        self, client, as_user, session, event_bus, user
    ):
        await make_api_service(session, event_bus).issue_new_key(
            user_id=user.id, key_name="cli_test", ttl=timedelta(days=1)
        )

        resp = await client.get(self._API_URL)

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "cli_test"
        assert body[0]["status"] == APIKeyStatus.ACTIVE.value
        assert "created_date" in body[0]

    async def test_delete_key_returns_204_and_deactivates(
        self, client, as_user, session, event_bus, user
    ):
        service = make_api_service(session, event_bus)
        await service.issue_new_key(
            user_id=user.id, key_name="to_delete", ttl=timedelta(days=1)
        )
        key_id = (await service.get_keys_by_user_id(user_id=user.id))[0].id

        resp = await client.delete(f"{self._API_URL}/{key_id}")

        assert resp.status_code == 204
        remaining = await service.get_keys_by_user_id(user_id=user.id)
        assert remaining[0].status == APIKeyStatus.INACTIVE

    async def test_issue_duplicate_active_name_returns_409(
        self, client, as_user, session, event_bus, user
    ):
        await make_api_service(session, event_bus).issue_new_key(
            user_id=user.id, key_name="dup", ttl=timedelta(days=1)
        )

        resp = await client.post(
            url=self._API_URL, json={"key_name": "dup", "ttl": "7d"}
        )

        assert resp.status_code == 409

    async def test_issue_key_requires_auth(self, client):
        resp = await client.post(
            url=self._API_URL, json={"key_name": "cli_test", "ttl": "7d"}
        )

        assert resp.status_code == 401
