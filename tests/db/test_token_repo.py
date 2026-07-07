import pytest

from datetime import timedelta, datetime, UTC
from src.repository.token_repo import PasswordSetTokenRepo
from src.domain.token import PasswordSetToken


@pytest.mark.integration
class TestTokenRepo:
    async def test_add_and_retrive_by_hash_success(self, session, user):
        repo = PasswordSetTokenRepo(session)

        raw, token = PasswordSetToken.issue(user.id)

        assert raw is not None
        assert isinstance(raw, str)
        assert isinstance(token, PasswordSetToken)
        assert token.used_at is None
        assert not token.is_used()
        assert not token.is_expired()

        await repo.add(token)

        from_db: PasswordSetToken | None = await repo.get_by_hash(token.token_hash)

        assert from_db is not None

    async def test_consume_and_update_success(self, session, user):
        repo = PasswordSetTokenRepo(session)

        raw, token = PasswordSetToken.issue(user.id)

        await repo.add(token)

        now = datetime.now(UTC)

        token.consume()

        assert token.is_used()

        await repo.update(token)

        from_db: PasswordSetToken | None = await repo.get_by_hash(token.token_hash)

        assert from_db is not None
        assert token.is_used()
        assert token.used_at is not None
        assert (token.used_at - now) < timedelta(seconds=0.1)
