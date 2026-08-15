import pytest
from datetime import timedelta

from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.api import api_key_router
from src.api.deps import get_api_service, get_current_user
from tests.conftest import make_api_service


@pytest.fixture
def app(session, event_bus, user) -> FastAPI:
    app = FastAPI()
    app.include_router(api_key_router.router)
    app.dependency_overrides[get_api_service] = lambda: make_api_service(
        session, event_bus
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestApiKeyRouter:
    _API_URL = "dutyy/api/v1/api-keys"

    async def test_issue_new_key_returns_201(self, client):
        resp = await client.post(
            url=self._API_URL, json={"key_name": "cli_test", "ttl": "7d"}
        )

        assert resp.status_code == 201
        assert "api-key" in resp.json()

    async def test_get_api_keys_success(self, client, session, event_bus, user):
        await make_api_service(session, event_bus).issue_new_key(
            user_id=user.id, key_name="cli_test", ttl=timedelta(days=1)
        )

        resp = await client.get(self._API_URL)

        assert resp.status_code == 200
        assert len(resp.json()) == 1
