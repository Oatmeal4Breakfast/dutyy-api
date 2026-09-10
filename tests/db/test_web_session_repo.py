from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from src.domain.session import SessionPolicy, WebSession
from src.repository.user_repo import UserRepo
from src.repository.web_session_repo import WebSessionRepo
from tests.conftest import make_user

_POLICY = SessionPolicy(
    idle_ttl=timedelta(minutes=30),
    absolute_ttl=timedelta(days=7),
    touch_interval=timedelta(minutes=5),
)


def make_web_session(user_id: UUID, **kwargs: Any) -> tuple[str, WebSession]:
    now: datetime = datetime.now(UTC)
    raw, session = WebSession.issue(user_id=user_id, policy=_POLICY, now=now)
    for key, value in kwargs.items():
        setattr(session, key, value)
    return raw, session


@pytest.mark.integration
class TestWebSessionRepo:
    async def test_add_and_get_by_token_hash(self, session, user, db_roundtrip):
        repo = WebSessionRepo(session)
        _, entity = make_web_session(user.id)
        await repo.add(entity)

        await db_roundtrip()
        result = await repo.get_by_token_hash(entity.token_hash)

        assert isinstance(result, WebSession)
        assert result is not entity
        assert result.token_hash == entity.token_hash
        assert result.user_id == user.id

    async def test_get_by_token_hash_not_found(self, session):
        repo = WebSessionRepo(session)

        assert await repo.get_by_token_hash("does_not_exist") is None

    async def test_update_persists_touch(self, session, user, db_roundtrip):
        repo = WebSessionRepo(session)
        _, entity = make_web_session(user.id)
        await repo.add(entity)

        touch_at = datetime.now(UTC) + timedelta(minutes=6)
        entity.touch(_POLICY, now=touch_at)
        await repo.update(entity)

        await db_roundtrip()
        result = await repo.get_by_token_hash(entity.token_hash)

        assert result.last_seen_at == touch_at

    async def test_revoke_sets_revoked_at(self, session, user, db_roundtrip):
        repo = WebSessionRepo(session)
        _, entity = make_web_session(user.id)
        await repo.add(entity)

        revoked = await repo.revoke(user.id, entity.token_hash)

        assert isinstance(revoked, WebSession)
        assert revoked.revoked_at is not None
        assert not revoked.is_active()

        await db_roundtrip()
        refetched = await repo.get_by_token_hash(entity.token_hash)
        assert refetched.revoked_at == revoked.revoked_at

    async def test_revoke_not_found_returns_none(self, session, user):
        repo = WebSessionRepo(session)

        assert await repo.revoke(user.id, "does_not_exist") is None

    async def test_revoke_foreign_user_returns_none(self, session, user):
        repo = WebSessionRepo(session)
        _, entity = make_web_session(user.id)
        await repo.add(entity)

        other = make_user(email="other@example.com")
        await UserRepo(session).add(other)

        assert await repo.revoke(other.id, entity.token_hash) is None

        still = await repo.get_by_token_hash(entity.token_hash)
        assert still.revoked_at is None

    async def test_revoke_idempotent_keeps_first_timestamp(
        self, session, user, db_roundtrip
    ):
        repo = WebSessionRepo(session)
        _, entity = make_web_session(user.id)
        await repo.add(entity)

        first = await repo.revoke(user.id, entity.token_hash)
        await db_roundtrip()
        second = await repo.revoke(user.id, entity.token_hash)

        assert first.revoked_at is not None
        assert second.revoked_at == first.revoked_at

    async def test_revoke_all_for_user(self, session, user):
        repo = WebSessionRepo(session)
        _, first = make_web_session(user.id)
        _, second = make_web_session(user.id)
        await repo.add(first)
        await repo.add(second)

        other = make_user(email="other@example.com")
        await UserRepo(session).add(other)
        _, foreign = make_web_session(other.id)
        await repo.add(foreign)

        await repo.revoke_all_for_user(user.id)

        assert (await repo.get_by_token_hash(first.token_hash)).revoked_at is not None
        assert (await repo.get_by_token_hash(second.token_hash)).revoked_at is not None
        assert (await repo.get_by_token_hash(foreign.token_hash)).revoked_at is None

    async def test_revoke_all_for_user_empty_noop(self, session, user):
        repo = WebSessionRepo(session)

        await repo.revoke_all_for_user(user.id)

        assert await repo.get_by_token_hash("does_not_exist") is None

    async def test_purge_removes_revoked_and_expired_keeps_active(self, session, user):
        repo = WebSessionRepo(session)
        now = datetime.now(UTC)

        _, revoked = make_web_session(user.id)
        revoked.revoke(now)
        await repo.add(revoked)

        _, idle_expired = make_web_session(
            user.id,
            idle_expires_at=now - timedelta(minutes=1),
            last_seen_at=now - timedelta(minutes=31),
        )
        await repo.add(idle_expired)

        _, absolute_expired = make_web_session(
            user.id,
            absolute_expires_at=now - timedelta(minutes=1),
        )
        await repo.add(absolute_expired)

        _, active = make_web_session(user.id)
        await repo.add(active)

        deleted = await repo.purge()

        assert deleted == 3
        assert await repo.get_by_token_hash(active.token_hash) is not None
        assert await repo.get_by_token_hash(revoked.token_hash) is None
        assert await repo.get_by_token_hash(idle_expired.token_hash) is None
        assert await repo.get_by_token_hash(absolute_expired.token_hash) is None
