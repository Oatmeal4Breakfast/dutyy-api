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
