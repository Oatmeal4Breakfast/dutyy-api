from typing import Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.deps import (
    get_api_service,
    get_current_user,
    get_device_auth_service,
)
from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.main import create_app
from src.repository.device_auth_repo import DeviceAuthRepo
from tests.conftest import make_api_service, make_device_auth_service


@pytest.fixture
def app(session, event_bus) -> Iterator[FastAPI]:
    app: FastAPI = create_app()
    app.dependency_overrides[get_device_auth_service] = lambda: (
        make_device_auth_service(session, event_bus)
    )
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
