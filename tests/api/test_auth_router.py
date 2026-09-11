from typing import Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pwdlib import PasswordHash

from src.api.deps import (
    get_api_service,
    get_auth_service,
    get_current_user,
    get_device_auth_service,
    get_web_session_config,
)
from src.config import WebSessionConfig
from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.main import create_app
from src.repository.device_auth_repo import DeviceAuthRepo
from src.repository.user_repo import UserRepo
from tests.conftest import (
    make_api_service,
    make_auth_service,
    make_device_auth_service,
)

TEST_SESSION_CONFIG = WebSessionConfig(cookie_name="dutyy-test-session", secure=False)
_hasher = PasswordHash.recommended()


@pytest.fixture
def app(session, event_bus) -> Iterator[FastAPI]:
    app: FastAPI = create_app()
    app.dependency_overrides[get_device_auth_service] = lambda: (
        make_device_auth_service(session, event_bus)
    )
    app.dependency_overrides[get_api_service] = lambda: make_api_service(
        session, event_bus
    )
    app.dependency_overrides[get_auth_service] = lambda: make_auth_service(
        session, event_bus
    )
    app.dependency_overrides[get_web_session_config] = lambda: TEST_SESSION_CONFIG
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


class TestDeviceAuthRouter:
    START = "/dutyy/api/v1/auth/device/code"
    TOKEN = "/dutyy/api/v1/auth/device/token"
    APPROVE = "/dutyy/api/v1/auth/device/auth"

    async def test_start_returns_device_code_payload(self, client):
        resp = await client.post(self.START, json={})

        assert resp.status_code == 200
        body = resp.json()
        assert body["device_code"]
        assert body["user_code"]
        assert body["verification_uri"]
        assert isinstance(body["expires_in"], int)
        assert isinstance(body["interval"], int)

    async def test_start_accepts_empty_body(self, client):
        resp = await client.post(self.START)

        assert resp.status_code == 200

    async def test_poll_pending_returns_authorization_pending(
        self, client, session, user
    ):
        raw, code = DeviceCode.issue()
        await DeviceAuthRepo(session).add(code)

        resp = await client.post(self.TOKEN, json={"device_code": raw})

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "authorization_pending"

    async def test_poll_unknown_device_code_returns_invalid_grant(self, client):
        resp = await client.post(self.TOKEN, json={"device_code": "not-real"})

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "invalid_grant"

    async def test_poll_approved_returns_token(self, client, session, user):
        raw, code = DeviceCode.issue()
        code.mark_approved(user.id)
        await DeviceAuthRepo(session).add(code)

        resp = await client.post(self.TOKEN, json={"device_code": raw})

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body["access_token"], str)
        assert body["access_token"]
        assert body["token_type"] == "bearer"

    async def test_approve_requires_auth(self, client, session):
        raw, code = DeviceCode.issue()
        await DeviceAuthRepo(session).add(code)

        resp = await client.post(self.APPROVE, json={"user_code": code.user_code})

        assert resp.status_code == 401

    async def test_approve_binds_user_and_returns_no_key(
        self, client, as_user, session, user
    ):
        raw, code = DeviceCode.issue()
        await DeviceAuthRepo(session).add(code)

        resp = await client.post(self.APPROVE, json={"user_code": code.user_code})

        assert resp.status_code == 200
        body = resp.json()
        assert "detail" in body
        assert "access_token" not in body
        assert "key" not in body

        persisted = await DeviceAuthRepo(session).get_code_by_hash(
            code.hashed_device_code
        )
        assert persisted.status == DeviceCodeStatus.APPROVED
        assert persisted.user_id == user.id

    async def test_approve_unknown_user_code_returns_400(self, client, as_user):
        resp = await client.post(self.APPROVE, json={"user_code": "ZZZZ-ZZZZ"})

        assert resp.status_code == 400


class TestBrowserAuthRouter:
    LOGIN = "/dutyy/api/v1/auth/login"
    SESSION = "/dutyy/api/v1/auth/session"
    LOGOUT = "/dutyy/api/v1/auth/logout"

    async def _with_password(self, session, user, password="correct-horse"):
        user.update_password_hash(_hasher.hash(password))
        await UserRepo(session).update(user)

    async def test_login_sets_cookie_and_returns_user(self, client, session, user):
        await self._with_password(session, user)

        resp = await client.post(
            self.LOGIN, json={"email": user.email, "password": "correct-horse"}
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_summary"]["email"] == user.email
        assert "access_token" not in body
        assert "raw_token" not in body
        set_cookie = resp.headers.get("set-cookie", "")
        assert TEST_SESSION_CONFIG.cookie_name in set_cookie
        assert "HttpOnly" in set_cookie
        assert "Secure" not in set_cookie
        assert resp.headers.get("cache-control") == "no-store"

    async def test_login_wrong_password_and_unknown_user_both_401(
        self, client, session, user
    ):
        await self._with_password(session, user)

        bad_password = await client.post(
            self.LOGIN, json={"email": user.email, "password": "wrong-password"}
        )
        unknown_user = await client.post(
            self.LOGIN, json={"email": "nobody@example.com", "password": "whatever"}
        )

        assert bad_password.status_code == 401
        assert unknown_user.status_code == 401
        assert bad_password.json() == unknown_user.json()

    async def test_session_restores_authenticated_user(self, client, session, user):
        await self._with_password(session, user)
        login_resp = await client.post(
            self.LOGIN, json={"email": user.email, "password": "correct-horse"}
        )
        assert login_resp.status_code == 200

        resp = await client.get(self.SESSION)

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_summary"]["email"] == user.email
        assert body["idle_expires_at"]
        assert body["absolute_expires_at"]
        assert resp.headers.get("cache-control") == "no-store"

    async def test_session_without_cookie_returns_401(self, client):
        resp = await client.get(self.SESSION)

        assert resp.status_code == 401

    async def test_session_with_forged_cookie_returns_401(self, client):
        client.cookies.set(TEST_SESSION_CONFIG.cookie_name, "forged-value")

        resp = await client.get(self.SESSION)

        assert resp.status_code == 401

    async def test_logout_clears_cookie_and_replay_fails(self, client, session, user):
        await self._with_password(session, user)
        login_resp = await client.post(
            self.LOGIN, json={"email": user.email, "password": "correct-horse"}
        )
        assert login_resp.status_code == 200

        resp = await client.post(self.LOGOUT)

        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-store"
        cleared = resp.headers.get("set-cookie", "")
        assert TEST_SESSION_CONFIG.cookie_name in cleared
        assert "Max-Age=0" in cleared

        replay = await client.get(self.SESSION)

        assert replay.status_code == 401

    async def test_logout_without_cookie_returns_401(self, client):
        resp = await client.post(self.LOGOUT)

        assert resp.status_code == 401
