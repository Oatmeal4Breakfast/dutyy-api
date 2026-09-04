from datetime import UTC, datetime, timedelta

import pytest

from src.domain.token import PasswordSetToken
from src.repository.token_repo import PasswordSetTokenRepo

_TTL = timedelta(minutes=15)


@pytest.mark.integration
class TestTokenRepo:
    async def test_add_and_retrive_by_hash_success(self, session, user, db_roundtrip):
        repo = PasswordSetTokenRepo(session)

        raw, token = PasswordSetToken.issue(user_id=user.id, ttl=_TTL)

        assert raw is not None
        assert isinstance(raw, str)
        assert isinstance(token, PasswordSetToken)
        assert token.used_at is None
        assert not token.is_used()
        assert not token.is_expired()

        await repo.add(token)

        await db_roundtrip()
        from_db: PasswordSetToken | None = await repo.get_by_hash(token.token_hash)

        assert from_db is not None
        assert from_db is not token
        assert from_db.user_id == user.id

    async def test_consume_and_update_success(self, session, user, db_roundtrip):
        repo = PasswordSetTokenRepo(session)

        raw, token = PasswordSetToken.issue(user_id=user.id, ttl=_TTL)

        await repo.add(token)

        now = datetime.now(UTC)

        token.consume()

        assert token.is_used()

        await repo.update(token)

        await db_roundtrip()
        from_db: PasswordSetToken | None = await repo.get_by_hash(token.token_hash)

        assert from_db is not None
        assert from_db.is_used()
        assert from_db.used_at is not None
        assert (from_db.used_at - now) < timedelta(seconds=0.1)

    async def test_get_active_by_user_id_excludes_used_and_expired(
        self, session, user, db_roundtrip
    ):
        repo = PasswordSetTokenRepo(session)

        _, active = PasswordSetToken.issue(user_id=user.id, ttl=_TTL)
        _, used = PasswordSetToken.issue(user_id=user.id, ttl=_TTL)
        _, expired = PasswordSetToken.issue(user_id=user.id, ttl=-_TTL)

        used.consume()

        for token in (active, used, expired):
            await repo.add(token)

        await db_roundtrip()
        results: list[PasswordSetToken] = await repo.get_active_by_user_id(user.id)

        assert [token.id for token in results] == [active.id]
