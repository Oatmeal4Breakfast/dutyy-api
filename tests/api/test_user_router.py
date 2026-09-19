from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.deps import get_auth_context, get_user_service
from src.config import WebSessionConfig
from src.domain.user import UserStatus
from src.main import create_app
from src.service.auth_service import AuthContext, CredentialMethod
from src.service.user_service import UserService
from tests.conftest import (
    make_api_service,
    make_auth_service,
    make_user_service,
)


@pytest.fixture
def app(session, event_bus, user_service) -> Iterator[FastAPI]:
    app = create_app()
    app.dependency_overrides[get_user_service] = lambda: user_service
    app.state.auth_service = make_auth_service(session, event_bus)
    app.state.api_service = make_api_service(session, event_bus)
    app.state.user_service = user_service
    app.state.web_session_config = WebSessionConfig(
        cookie_name="dutyy-test-session", secure=False
    )
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def user_service(session, event_bus) -> UserService:
    return make_user_service(session, event_bus)


@pytest.fixture
def as_user(app, user) -> FastAPI:
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user=user.to_summary(),
        method=CredentialMethod.SESSION,
        credential_id=user.id,
    )
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client


class TestUserRouter:
    _USERS_URL = "/dutyy/api/v1/users"
    _ME_URL = f"{_USERS_URL}/me"

    async def test_get_user_returns_user(self, client, as_user, user):
        response = await client.get(self._ME_URL)

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email
        assert body["status"] == UserStatus.ACTIVE

    async def test_create_user_is_public(self, client, user_service):
        response = await client.post(
            self._USERS_URL,
            json={
                "first_name": " New ",
                "last_name": " User ",
                "email": "new.user@example.com",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["first_name"] == "New"
        assert body["last_name"] == "User"
        assert body["email"] == "new.user@example.com"

    async def test_update_user_changes_fields(self, client, as_user, user):
        response = await client.patch(
            self._ME_URL,
            json={
                "first_name": " Updated ",
                "email": "updated@example.com",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["first_name"] == "Updated"
        assert body["email"] == "updated@example.com"

    async def test_empty_update_returns_400(self, client, as_user, user):
        response = await client.patch(self._ME_URL, json={})

        assert response.status_code == 400
        assert response.json() == {"detail": "no fields provided to update"}

    async def test_protected_user_routes_require_authentication(self, client, user):
        response = await client.get(self._ME_URL)

        assert response.status_code == 401
