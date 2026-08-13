import pytest

from datetime import datetime, timedelta, UTC

from structlog.testing import capture_logs

from tests.conftest import make_api_service

from src.service.api_service import APIService
from src.domain.api import APIKey, APIKeyStatus
from src.repository.api_repo import APIRepo


@pytest.mark.integration
class TestAPIService:
    async def test_issue_new_key_success(self, user, session, event_bus):
        repo = APIRepo(session)
        service: APIService = make_api_service(session, event_bus)
        with capture_logs() as logs:
            raw_new_key: str = await service.issue_new_key(
                user_id=user.id, key_name="test", ttl=timedelta(days=7)
            )

            assert any(
                log["event"] == "new_api_key_generated" and log["log_level"] == "info"
                for log in logs
            )
        is_persisted: APIKey | None = await repo.get_by_hash(
            hash=APIKey.hash_key(raw_new_key)
        )
        assert isinstance(raw_new_key, str)
        assert is_persisted is not None
        assert isinstance(is_persisted, APIKey)
        assert datetime.now(UTC) - is_persisted.created_date < timedelta(seconds=0.1)

    async def test_verify_valid_key_with_valid_user_success(
        self, user, session, event_bus
    ):
        service: APIService = make_api_service(session, event_bus)

        raw_key: str = await service.issue_new_key(
            user_id=user.id, key_name="test", ttl=timedelta(days=7)
        )

        key: APIKey | None = await service.verify(raw_key)

        assert isinstance(key, APIKey)
        assert key.user_id == user.id
        assert key.last_used is not None
        assert datetime.now(UTC) - key.last_used < timedelta(seconds=0.1)

    async def test_veryfy_key_not_found(self, user, session, event_bus):
        service: APIService = make_api_service(session, event_bus)
        raw, key = APIKey.issue(user_id=user.id, name="test_key", ttl=timedelta(days=7))

        assert key.key_hash is not None
        assert await service.verify(raw) is None

    async def test_verify_returns_none_for_invalid_key(
        self, user, session, event_bus, api_key
    ):
        repo = APIRepo(session)
        service: APIService = make_api_service(session, event_bus)
        raw, key = APIKey.issue(user_id=user.id, name="test_key", ttl=timedelta(days=7))

        key.status = APIKeyStatus.INACTIVE

        await repo.add(key)

        test_results: APIKey | None = await service.verify(raw)

        assert test_results is None

    async def test_verify_returns_none_for_no_expiry_date(
        self, user, session, event_bus
    ):
        repo = APIRepo(session)
        service: APIService = make_api_service(session, event_bus)

        raw, key = APIKey.issue(user_id=user.id, name="test_key", ttl=timedelta(days=1))

        key.expires_at = None

        await repo.add(key)

        assert await service.verify(raw) is None

    async def test_verify_returns_none_for_expired_key(self, user, session, event_bus):
        repo = APIRepo(session)
        service: APIService = make_api_service(session, event_bus)

        raw, key = APIKey.issue(
            user_id=user.id, name="test_key", ttl=timedelta(microseconds=1)
        )

        await repo.add(key)

        assert await service.verify(raw) is None

    async def test_revoke_success(self, user, session, event_bus):
        repo = APIRepo(session)
        service: APIService = make_api_service(session, event_bus)

        raw: str = await service.issue_new_key(
            user_id=user.id, key_name="test_key", ttl=timedelta(days=1)
        )

        key: APIKey | None = await service.verify(raw)

        assert key is not None

        await service.revoke(user_id=user.id, key_id=key.id)

        persisted = await repo.get_by_hash(key.key_hash)

        assert persisted is not None
        assert persisted.status == APIKeyStatus.INACTIVE
