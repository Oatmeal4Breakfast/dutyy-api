from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid7

import pytest
from fastapi import HTTPException, Request
from pwdlib import PasswordHash

from src.api.deps import (
    get_api_key,
    get_api_key_user,
    get_auth_context,
    get_optional_api_key,
    get_optional_session,
    require_allowed_origin,
    require_csrf_token,
)
from src.config import WebSessionConfig
from src.domain.api import APIKey
from src.domain.user import UserStatus, UserSummary
from src.repository.user_repo import UserRepo
from src.service.api_service import APIService
from src.service.auth_service import AuthContext, CredentialMethod, SessionState
from src.service.user_service import UserService
from tests.conftest import make_api_service, make_auth_service, make_user_service

_hasher = PasswordHash.recommended()
_TEST_COOKIE = WebSessionConfig().cookie_name


def make_request(headers: dict[str, str], method: str = "GET") -> Request:
    scope: dict[str, Any] = {
        "type": "http",
        "method": method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope=scope)


def make_session_state(csrf_token: str = "csrf-token") -> SessionState:
    now = datetime.now(UTC)
    return SessionState(
        user_summary=UserSummary(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            last_login=None,
            modified_date=None,
            created_date=now,
            status=UserStatus.ACTIVE,
            id=uuid7(),
        ),
        idle_expires_at=now + timedelta(minutes=30),
        absolute_expires_at=now + timedelta(days=7),
        csrf_token=csrf_token,
        session_id=uuid7(),
    )


def make_auth_context(method: CredentialMethod) -> AuthContext:
    session = make_session_state()
    return AuthContext(
        user=session.user_summary,
        method=method,
        credential_id=session.session_id,
    )


def test_require_allowed_origin_accepts_configured_origin() -> None:
    request = make_request({"Origin": "https://dutyy.app"}, method="POST")

    require_allowed_origin(
        request,
        config=WebSessionConfig(),
        allowed_origins=frozenset({"https://dutyy.app"}),
    )


@pytest.mark.parametrize("origin", [None, "https://evil.example"])
def test_require_allowed_origin_rejects_untrusted_origin(origin: str | None) -> None:
    headers = {} if origin is None else {"Origin": origin}
    request = make_request(headers, method="POST")

    with pytest.raises(HTTPException) as exc:
        require_allowed_origin(
            request,
            config=WebSessionConfig(),
            allowed_origins=frozenset({"https://dutyy.app"}),
        )

    assert exc.value.status_code == 403


def test_require_allowed_origin_skips_api_key_without_session_cookie() -> None:
    request = make_request(
        {"X-API-Key": "dty_test_key"},
        method="POST",
    )

    require_allowed_origin(
        request,
        config=WebSessionConfig(),
        allowed_origins=frozenset({"https://dutyy.app"}),
    )


async def test_require_csrf_token_accepts_matching_session_token() -> None:
    request = make_request({"X-CSRF-Token": "csrf-token"}, method="POST")

    await require_csrf_token(
        request,
        ctx=make_auth_context(CredentialMethod.SESSION),
        session=make_session_state(),
    )


@pytest.mark.parametrize("headers", [{}, {"X-CSRF-Token": "wrong-token"}])
async def test_require_csrf_token_rejects_missing_or_invalid_token(
    headers: dict[str, str],
) -> None:
    request = make_request(headers, method="POST")

    with pytest.raises(HTTPException) as exc:
        await require_csrf_token(
            request,
            ctx=make_auth_context(CredentialMethod.SESSION),
            session=make_session_state(),
        )

    assert exc.value.status_code == 403


async def test_require_csrf_token_skips_safe_methods() -> None:
    request = make_request({}, method="GET")

    await require_csrf_token(
        request,
        ctx=make_auth_context(CredentialMethod.SESSION),
        session=make_session_state(),
    )


async def test_require_csrf_token_skips_api_key_authentication() -> None:
    request = make_request({}, method="POST")

    await require_csrf_token(
        request,
        ctx=make_auth_context(CredentialMethod.API),
        session=None,
    )


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
        config = WebSessionConfig()
        return await get_auth_context(
            request=request,
            config=config,
            api_key=await get_optional_api_key(request, api_service),
            session=await get_optional_session(request, config, auth_service),
            user_service=user_service,
            allowed_origins=frozenset({"http://test"}),
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
