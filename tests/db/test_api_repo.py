from datetime import UTC, datetime, timedelta

import pytest

from src.domain.api import APIKey, APIKeyStatus, APIKeySummary
from src.repository.api_repo import APIRepo
from tests.conftest import make_api_key


@pytest.mark.integration
class TestAPIRepo:
    async def test_add_and_get_by_user_id(self, session, api_key, user):
        repo = APIRepo(session)

        results: list[APIKeySummary] = await repo.get_by_user_id(user.id)

        assert len(results) == 1
        assert isinstance(results[0], APIKeySummary)
        assert results[0].id == api_key.id
        assert results[0].status == api_key.status

    async def test_get_by_user_id_returns_empty_list(self, session, user):
        repo = APIRepo(session)

        results: list[APIKeySummary] = await repo.get_by_user_id(user.id)

        assert isinstance(results, list)
        assert len(results) == 0

    async def test_get_by_user_id_returns_multiple(self, session, api_key, user):
        repo = APIRepo(session)

        second_key = make_api_key(user.id, name="ipad")
        await repo.add(second_key)

        results: list[APIKeySummary] = await repo.get_by_user_id(user.id)

        assert len(results) == 2

    async def test_update_api_key(self, session, api_key, user, db_roundtrip):
        repo = APIRepo(session)

        assert api_key.status == APIKeyStatus.ACTIVE

        api_key.mark_inactive()
        await repo.update(api_key)

        await db_roundtrip()
        results: list[APIKeySummary] = await repo.get_by_user_id(user.id)

        assert len(results) == 1
        assert results[0].status == APIKeyStatus.INACTIVE

    async def test_mark_expired_updates_elapsed_active_key(
        self, session, user, db_roundtrip
    ):
        repo = APIRepo(session)
        now = datetime.now(UTC)
        key = make_api_key(
            user.id,
            expires_at=now - timedelta(seconds=1),
        )
        await repo.add(key)

        result = await repo.mark_expired(key.id, user.id)
        await db_roundtrip()
        persisted = await repo.get_by_id(key.id, user.id)

        assert result is not None
        assert persisted is not None
        assert persisted.status == APIKeyStatus.EXPIRED

    async def test_mark_expired_ignores_key_that_has_not_elapsed(self, session, user):
        repo = APIRepo(session)
        now = datetime.now(UTC)
        key = make_api_key(
            user.id,
            expires_at=now + timedelta(days=1),
        )
        await repo.add(key)

        result = await repo.mark_expired(key.id, user.id)

        assert result is None
        assert key.status == APIKeyStatus.ACTIVE

    async def test_mark_expired_for_user_can_filter_by_name(self, session, user):
        repo = APIRepo(session)
        now = datetime.now(UTC)
        matching = make_api_key(
            user.id,
            name="matching",
            key_hash="matching_hash",
            expires_at=now - timedelta(seconds=1),
        )
        other = make_api_key(
            user.id,
            name="other",
            key_hash="other_hash",
            expires_at=now - timedelta(seconds=1),
        )
        await repo.add(matching)
        await repo.add(other)

        count = await repo.mark_expired_for_user(user.id, now, key_name=matching.name)

        assert count == 1
        assert matching.status == APIKeyStatus.EXPIRED
        assert other.status == APIKeyStatus.ACTIVE

    async def test_get_api_key_by_hash_success(self, session, api_key, db_roundtrip):
        repo = APIRepo(session)
        await db_roundtrip()

        test_results: APIKey | None = await repo.get_by_hash(api_key.key_hash)

        assert isinstance(test_results, APIKey)
        assert test_results is not api_key
        assert test_results.key_hash == api_key.key_hash

    async def test_get_api_key_by_id_success(
        self, session, api_key, user, db_roundtrip
    ):
        repo = APIRepo(session)
        await db_roundtrip()

        result: APIKey | None = await repo.get_by_id(
            key_id=api_key.id, owner_id=user.id
        )

        assert isinstance(result, APIKey)
        assert result is not api_key
        assert result.id == api_key.id

    async def test_get_api_key_by_id_returns_none(self, session, user):
        from uuid import uuid7

        repo = APIRepo(session)

        assert await repo.get_by_id(key_id=uuid7(), owner_id=user.id) is None

    async def test_get_api_key_by_id_returns_none_for_wrong_owner(
        self, session, api_key
    ):
        from uuid import uuid7

        repo = APIRepo(session)

        assert await repo.get_by_id(key_id=api_key.id, owner_id=uuid7()) is None
