import pytest

from src.repository.api_repo import APIRepo
from src.domain.api import APIKey, APIKeyStatus, APIKeySummary
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

    async def test_update_api_key(self, session, api_key, user):
        repo = APIRepo(session)

        assert api_key.status == APIKeyStatus.ACTIVE

        api_key.mark_inactive()
        await repo.update(api_key)

        results: list[APIKeySummary] = await repo.get_by_user_id(user.id)

        assert len(results) == 1
        assert results[0].status == APIKeyStatus.INACTIVE

    async def test_get_api_key_by_hash_success(self, session, api_key):
        repo = APIRepo(session)

        test_results: APIKey | None = await repo.get_by_hash(api_key.key_hash)

        assert isinstance(test_results, APIKey)
        assert test_results.key_hash == api_key.key_hash
