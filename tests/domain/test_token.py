import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid7

import pytest

from src.domain.exceptions import DomainValidationError
from src.domain.token import PasswordSetToken

_DEFAULT_USER_ID = uuid7()
_TTL = timedelta(minutes=15)


def make_token(**kwargs) -> PasswordSetToken:
    now = datetime.now(UTC)
    defaults: dict[str, Any] = {
        "user_id": _DEFAULT_USER_ID,
        "token_hash": "hashed_token_abc123",
        "created_date": now,
        "expires_at": now + timedelta(minutes=30),
    }
    return PasswordSetToken(**{**defaults, **kwargs})


def test_create_token_success() -> None:
    token = make_token()

    assert isinstance(token, PasswordSetToken)
    assert token.token_hash == "hashed_token_abc123"
    assert token.user_id == _DEFAULT_USER_ID
    assert token.used_at is None


def test_token_belongs_to_user() -> None:
    user_id = uuid7()
    token = make_token(user_id=user_id)
    assert token.user_id == user_id


def test_token_unique_ids() -> None:
    token_one = make_token()
    token_two = make_token()
    assert token_one.id != token_two.id


def test_issue_returns_raw_token_and_entity() -> None:
    raw_token, token = PasswordSetToken.issue(user_id=_DEFAULT_USER_ID, ttl=_TTL)

    assert isinstance(raw_token, str)
    assert raw_token
    assert isinstance(token, PasswordSetToken)
    assert token.user_id == _DEFAULT_USER_ID


def test_issue_stores_hash_not_raw_token() -> None:
    raw_token, token = PasswordSetToken.issue(user_id=_DEFAULT_USER_ID, ttl=_TTL)

    assert token.token_hash != raw_token
    assert token.token_hash == hashlib.sha256(raw_token.encode()).hexdigest()


def test_issue_sets_expiry_relative_to_created_date() -> None:
    _, token = PasswordSetToken.issue(user_id=_DEFAULT_USER_ID, ttl=_TTL)

    time_diff = datetime.now(UTC) - token.created_date
    assert time_diff < timedelta(seconds=1)
    assert token.expires_at == token.created_date + _TTL


def test_issue_generates_unique_tokens() -> None:
    raw_one, token_one = PasswordSetToken.issue(user_id=_DEFAULT_USER_ID, ttl=_TTL)
    raw_two, token_two = PasswordSetToken.issue(user_id=_DEFAULT_USER_ID, ttl=_TTL)

    assert raw_one != raw_two
    assert token_one.token_hash != token_two.token_hash
    assert token_one.id != token_two.id


def test_is_expired_true_when_now_past_expiry() -> None:
    expires = datetime.now(UTC)
    token = make_token(expires_at=expires)
    assert token.is_expired(now=expires + timedelta(seconds=1)) is True


def test_is_expired_false_when_now_before_expiry() -> None:
    expires = datetime.now(UTC)
    token = make_token(expires_at=expires)
    assert token.is_expired(now=expires - timedelta(seconds=1)) is False


def test_is_expired_defaults_to_current_time() -> None:
    fresh = make_token(expires_at=datetime.now(UTC) + timedelta(minutes=30))
    stale = make_token(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    assert fresh.is_expired() is False
    assert stale.is_expired() is True


def test_is_used_false_when_unconsumed() -> None:
    token = make_token()
    assert token.is_used() is False


def test_is_used_true_when_consumed() -> None:
    token = make_token(used_at=datetime.now(UTC))
    assert token.is_used() is True


def test_consume_marks_token_used() -> None:
    token = make_token()

    token.consume()

    assert token.is_used() is True
    time_diff = datetime.now(UTC) - token.used_at
    assert time_diff < timedelta(seconds=1)


def test_consume_already_used_fails() -> None:
    token = make_token(used_at=datetime.now(UTC))
    with pytest.raises(DomainValidationError):
        token.consume()


def test_consume_expired_fails() -> None:
    token = make_token(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    with pytest.raises(DomainValidationError):
        token.consume()


def test_consume_is_single_use() -> None:
    token = make_token()

    token.consume()
    with pytest.raises(DomainValidationError):
        token.consume()
