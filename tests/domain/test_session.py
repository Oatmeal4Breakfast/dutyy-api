from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid7

import pytest

from src.domain.exceptions import DomainValidationError
from src.domain.session import SessionPolicy, WebSession

_DEFAULT_USER_ID = uuid7()


def make_web_session(**kwargs) -> WebSession:
    now: datetime = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "user_id": _DEFAULT_USER_ID,
        "token_hash": "hashed_token_abc123",
        "absolute_expires_at": now + timedelta(minutes=15),
        "idle_expires_at": now + timedelta(minutes=5),
        "last_seen_at": now,
        "created_at": now,
    }
    return WebSession(**{**defaults, **kwargs})


def test_create_web_session_success() -> None:
    session = make_web_session()
    time_diff = datetime.now(UTC) - session.created_at

    assert time_diff < timedelta(seconds=1)
    assert isinstance(session, WebSession)
    assert session.revoked_at is None


def test_create_web_session_empty_token_hash_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_web_session(token_hash="")


def test_web_session_unique_ids() -> None:
    session_one = make_web_session()
    session_two = make_web_session()
    assert session_one.id != session_two.id


def test_revoked_returns_not_active() -> None:
    now = datetime.now(UTC)
    session = make_web_session(revoked_at=now)

    assert not session.is_active()


def test_past_abs_expires_not_active() -> None:
    session = make_web_session()
    session.absolute_expires_at = datetime.now(UTC) - timedelta(minutes=30)

    assert not session.is_active()


def test_past_idle_expires_not_active() -> None:
    session = make_web_session()
    session.idle_expires_at = datetime.now(UTC) - timedelta(minutes=30)

    assert not session.is_active()


def test_touch_fails_on_inactive_session() -> None:
    session = make_web_session()
    session.idle_expires_at = datetime.now(UTC) - timedelta(minutes=30)
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    with pytest.raises(DomainValidationError):
        session.touch(policy)


def test_touch_within_throttle_idempotent() -> None:
    session = make_web_session()

    last_touch = session.last_seen_at

    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )
    now = datetime.now(UTC) + timedelta(minutes=4, seconds=55)
    idle_before = session.idle_expires_at
    session.touch(policy, now=now)

    assert session.last_seen_at == last_touch
    assert session.idle_expires_at == idle_before


def test_touch_cannot_exceed_absolute() -> None:
    now_base = datetime.now(UTC)
    session = make_web_session(
        created_at=now_base,
        last_seen_at=now_base,
        idle_expires_at=now_base + timedelta(minutes=40),
        absolute_expires_at=now_base + timedelta(minutes=50),
    )
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    old_idle = session.idle_expires_at
    touch_now = now_base + timedelta(minutes=25)
    session.touch(policy=policy, now=touch_now)

    assert old_idle < session.idle_expires_at
    assert session.absolute_expires_at == session.idle_expires_at


def test_touch_happy_path() -> None:
    now_base = datetime.now(UTC)
    session = make_web_session(
        created_at=now_base,
        last_seen_at=now_base,
        idle_expires_at=now_base + timedelta(minutes=40),
        absolute_expires_at=now_base + timedelta(days=7),
    )
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    t0 = session.idle_expires_at

    touch_now = now_base + timedelta(minutes=6)
    session.touch(policy=policy, now=touch_now)

    assert t0 != session.idle_expires_at
    assert session.last_seen_at == touch_now
    assert session.idle_expires_at != session.absolute_expires_at
    assert session.idle_expires_at == touch_now + policy.idle_ttl


def test_issue_success() -> None:
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )
    now = datetime.now(UTC)

    raw, session = WebSession.issue(user_id=_DEFAULT_USER_ID, policy=policy, now=now)

    assert WebSession.hash_token(raw) == session.token_hash

    assert session.user_id == _DEFAULT_USER_ID
    assert session.last_seen_at == now
    assert session.revoked_at is None
    assert session.idle_expires_at == now + policy.idle_ttl
    assert session.absolute_expires_at == now + policy.absolute_ttl
    assert session.is_active(now)


def test_revoke_success() -> None:
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    now = datetime.now(UTC)

    _, session = WebSession.issue(user_id=_DEFAULT_USER_ID, policy=policy, now=now)

    session.revoke(now)

    assert session.revoked_at == now
    assert not session.is_active()

    with pytest.raises(DomainValidationError):
        session.touch(policy=policy, now=now)


def test_revoke_idempotent_keeps_first_timestamp() -> None:
    session = make_web_session()
    first = datetime.now(UTC)
    second = first + timedelta(minutes=1)

    session.revoke(first)
    session.revoke(second)

    assert session.revoked_at == first


def test_revoke_defaults_to_now() -> None:
    session = make_web_session()
    before = datetime.now(UTC)

    session.revoke()

    assert session.revoked_at is not None
    assert before <= session.revoked_at <= datetime.now(UTC)
    assert not session.is_active()


def test_hash_token_deterministic_and_unique() -> None:
    assert WebSession.hash_token("abc") == WebSession.hash_token("abc")
    assert WebSession.hash_token("abc") != WebSession.hash_token("abd")


@pytest.mark.parametrize(
    "idle_ttl, absolute_ttl, touch_interval",
    [
        (timedelta(minutes=30), timedelta(days=7), timedelta(0)),
        (timedelta(minutes=30), timedelta(days=7), timedelta(minutes=30)),
        (timedelta(minutes=30), timedelta(days=7), timedelta(hours=1)),
        (timedelta(days=8), timedelta(days=7), timedelta(minutes=5)),
    ],
)
def test_session_policy_invalid(
    idle_ttl: timedelta, absolute_ttl: timedelta, touch_interval: timedelta
) -> None:
    with pytest.raises(DomainValidationError):
        SessionPolicy(
            idle_ttl=idle_ttl,
            absolute_ttl=absolute_ttl,
            touch_interval=touch_interval,
        )


def test_create_fails_when_created_after_last_seen() -> None:
    now_base = datetime.now(UTC)
    with pytest.raises(DomainValidationError):
        make_web_session(
            created_at=now_base + timedelta(minutes=1),
            last_seen_at=now_base,
            idle_expires_at=now_base + timedelta(minutes=40),
            absolute_expires_at=now_base + timedelta(minutes=50),
        )


def test_create_fails_when_last_seen_not_before_idle() -> None:
    now_base = datetime.now(UTC)
    with pytest.raises(DomainValidationError):
        make_web_session(
            created_at=now_base,
            last_seen_at=now_base,
            idle_expires_at=now_base,
            absolute_expires_at=now_base + timedelta(minutes=50),
        )


def test_create_fails_when_idle_after_absolute() -> None:
    now_base = datetime.now(UTC)
    with pytest.raises(DomainValidationError):
        make_web_session(
            created_at=now_base,
            last_seen_at=now_base,
            idle_expires_at=now_base + timedelta(minutes=50),
            absolute_expires_at=now_base + timedelta(minutes=40),
        )


def test_create_fails_on_whitespace_token_hash() -> None:
    with pytest.raises(DomainValidationError):
        make_web_session(token_hash="   ")


def test_create_strips_token_hash() -> None:
    session = make_web_session(token_hash="  hashed_token_abc123  ")

    assert session.token_hash == "hashed_token_abc123"


def test_touch_at_exact_interval_proceeds() -> None:
    now_base = datetime.now(UTC)
    session = make_web_session(
        created_at=now_base,
        last_seen_at=now_base,
        idle_expires_at=now_base + timedelta(minutes=40),
        absolute_expires_at=now_base + timedelta(days=7),
    )
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    touch_now = now_base + timedelta(minutes=5)
    session.touch(policy=policy, now=touch_now)

    assert session.last_seen_at == touch_now
    assert session.idle_expires_at == touch_now + policy.idle_ttl


def test_touch_exact_absolute_boundary_caps() -> None:
    now_base = datetime.now(UTC)
    session = make_web_session(
        created_at=now_base,
        last_seen_at=now_base,
        idle_expires_at=now_base + timedelta(minutes=40),
        absolute_expires_at=now_base + timedelta(minutes=50),
    )
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    # 20m + 30m idle == 50m absolute exactly -> should take the cap branch.
    touch_now = now_base + timedelta(minutes=20)
    session.touch(policy=policy, now=touch_now)

    assert session.last_seen_at == touch_now
    assert session.idle_expires_at == session.absolute_expires_at


def test_touch_fails_on_absolute_expired_session() -> None:
    session = make_web_session()
    session.absolute_expires_at = datetime.now(UTC) - timedelta(minutes=30)
    policy = SessionPolicy(
        idle_ttl=timedelta(minutes=30),
        absolute_ttl=timedelta(days=7),
        touch_interval=timedelta(minutes=5),
    )

    with pytest.raises(DomainValidationError):
        session.touch(policy)
