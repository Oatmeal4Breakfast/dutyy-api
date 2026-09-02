from datetime import timedelta
from typing import Any

import pytest
from fastapi import HTTPException, Request

from src.api.deps import get_api_key, get_api_key_user
from src.domain.api import APIKey
from src.service.api_service import APIService
from src.service.user_service import UserService
from tests.conftest import make_api_service, make_user_service


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
