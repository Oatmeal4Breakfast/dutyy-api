from datetime import timedelta
from typing import Any

import pytest
from fastapi import HTTPException, Request
from pwdlib import PasswordHash

from src.api.deps import (
    get_api_key,
    get_api_key_user,
    get_auth_context,
    get_optional_api_key,
    get_optional_session,
)
from src.config import WebSessionConfig
from src.domain.api import APIKey
from src.domain.user import UserStatus
from src.repository.user_repo import UserRepo
from src.service.api_service import APIService
from src.service.auth_service import CredentialMethod
from src.service.user_service import UserService
from tests.conftest import make_api_service, make_auth_service, make_user_service

_hasher = PasswordHash.recommended()
_TEST_COOKIE = WebSessionConfig().cookie_name


def make_request(headers: dict[str, str]) -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope=scope)


class TestDeps:
    async def test_get_api_key_success(self, session, event_bus, user):
        service: APIService = make_api_service(session, event_bus)

        raw = await service.issue_new_key(
            user_id=user.id, key_name="cli", ttl=timedelta(days=1)
        )
        headers = {"X-API-Key": raw}
        request = make_request(headers=headers)

        test_results = await get_api_key(request=request, service=service)

        assert isinstance(test_results, APIKey)
        assert test_results.key_hash == APIKey.hash_key(raw)
        assert test_results.user_id == user.id

    async def test_get_api_key_key_not_found(self, session, event_bus, user):
        service: APIService = make_api_service(session, event_bus)

        request = make_request({})

        with pytest.raises(HTTPException) as exc:
            await get_api_key(request, service)

        assert exc.value.status_code == 401

    async def test_get_api_key_not_real(self, session, event_bus, user):
        service: APIService = make_api_service(session, event_bus)

        raw, _ = APIKey.issue(
            user_id=user.id, name="failing_token", ttl=timedelta(days=1)
        )

        request = make_request(headers={"X-API-Key": raw})

        with pytest.raises(HTTPException) as exc:
            await get_api_key(request, service)

        assert exc.value.status_code == 401

    async def test_get_api_key_user_success(self, session, user, event_bus):
        api_service: APIService = make_api_service(session, event_bus)
        user_service: UserService = make_user_service(session, event_bus)

        raw: str = await api_service.issue_new_key(
            user_id=user.id, key_name="test_key", ttl=timedelta(days=1)
        )

        request = make_request(headers={"X-API-Key": raw})

        key: APIKey = await get_api_key(request, service=api_service)
        user = await get_api_key_user(key=key, service=user_service)


class TestAuthContext:
    async def _login(self, session, event_bus, user, password="correct-horse"):
        user.update_password_hash(_hasher.hash(password))
        await UserRepo(session).update(user)
        auth_service = make_auth_service(session, event_bus)
        login = await auth_service.login(user.email, password)
        assert login is not None
        return auth_service, login

    async def _context(self, session, event_bus, headers):
        request = make_request(headers=headers)
        api_service = make_api_service(session, event_bus)
        auth_service = make_auth_service(session, event_bus)
        user_service = make_user_service(session, event_bus)
        return await get_auth_context(
            api_key=await get_optional_api_key(request, api_service),
            session=await get_optional_session(
                request, WebSessionConfig(), auth_service
            ),
            user_service=user_service,
        )

    async def test_session_credential_builds_session_context(
        self, session, event_bus, user
    ):
        _, login = await self._login(session, event_bus, user)

        ctx = await self._context(
            session, event_bus, {"cookie": f"{_TEST_COOKIE}={login.raw_token}"}
        )

        assert ctx.method == CredentialMethod.SESSION
        assert ctx.user.id == user.id
        assert ctx.credential_id == login.session.id

    async def test_api_key_credential_builds_api_context(
        self, session, event_bus, user
    ):
        api_service = make_api_service(session, event_bus)
        raw = await api_service.issue_new_key(
            user_id=user.id, key_name="cli", ttl=timedelta(days=1)
        )

        ctx = await self._context(session, event_bus, {"X-API-Key": raw})

        assert ctx.method == CredentialMethod.API
        assert ctx.user.id == user.id

    async def test_both_credentials_returns_401(self, session, event_bus, user):
        _, login = await self._login(session, event_bus, user)
        api_service = make_api_service(session, event_bus)
        raw = await api_service.issue_new_key(
            user_id=user.id, key_name="cli", ttl=timedelta(days=1)
        )

        with pytest.raises(HTTPException) as exc:
            await self._context(
                session,
                event_bus,
                {
                    "cookie": f"{_TEST_COOKIE}={login.raw_token}",
                    "X-API-Key": raw,
                },
            )

        assert exc.value.status_code == 401

    async def test_no_credential_returns_401(self, session, event_bus):
        with pytest.raises(HTTPException) as exc:
            await self._context(session, event_bus, {})

        assert exc.value.status_code == 401

    async def test_blocked_owner_api_key_returns_401(self, session, event_bus, user):
        api_service = make_api_service(session, event_bus)
        raw = await api_service.issue_new_key(
            user_id=user.id, key_name="cli", ttl=timedelta(days=1)
        )
        user.update_status(status=UserStatus.BLOCKED)
        await UserRepo(session).update(user)

        with pytest.raises(HTTPException) as exc:
            await self._context(session, event_bus, {"X-API-Key": raw})

        assert exc.value.status_code == 401
