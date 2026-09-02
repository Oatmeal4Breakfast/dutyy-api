from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid7

import pytest

from src.domain.api import APIKey
from src.domain.exceptions import DomainValidationError

_DEFAULT_USER_ID = uuid7()


def make_api_key(**kwargs) -> APIKey:
    defaults: dict[str, Any] = {
        "user_id": _DEFAULT_USER_ID,
        "key_hash": "hashed_key_abc123",
        "name": "macbook",
    }
    return APIKey(**{**defaults, **kwargs})


def test_create_api_key_success() -> None:
    api_key = make_api_key()

    time_diff = datetime.now(UTC) - api_key.created_date
    assert time_diff < timedelta(seconds=1)
    assert isinstance(api_key, APIKey)
    assert api_key.key_hash == "hashed_key_abc123"
    assert api_key.name == "macbook"
    assert api_key.last_used is None
    assert api_key.expires_at is None


def test_create_api_key_normalizes_whitespace() -> None:
    api_key = make_api_key(key_hash="  hashed_key_abc123  ", name="  macbook  ")
    assert api_key.key_hash == "hashed_key_abc123"
    assert api_key.name == "macbook"


def test_create_api_key_empty_hash_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_api_key(key_hash="")


def test_create_api_key_whitespace_hash_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_api_key(key_hash="   ")


def test_create_api_key_empty_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_api_key(name="")


def test_create_api_key_whitespace_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_api_key(name="   ")


def test_api_key_unique_ids() -> None:
    key_one = make_api_key()
    key_two = make_api_key()
    assert key_one.id != key_two.id


def test_api_key_with_expiry() -> None:
    expires = datetime.now(UTC) + timedelta(days=30)
    api_key = make_api_key(expires_at=expires)
    assert api_key.expires_at == expires


def test_api_key_belongs_to_user() -> None:
    user_id = uuid7()
    api_key = make_api_key(user_id=user_id)
    assert api_key.user_id == user_id


def test_mark_inactive_changes_status() -> None:
    from src.domain.api import APIKeyStatus

    api_key = make_api_key()

    assert api_key.status == APIKeyStatus.ACTIVE

    api_key.mark_inactive()

    assert api_key.status == APIKeyStatus.INACTIVE


def test_issue_success(user) -> None:
    raw_key, key = APIKey.issue(
        user_id=user.id, name="macbook_pro", ttl=timedelta(days=90)
    )
    now = datetime.now(UTC)
    assert isinstance(raw_key, str)
    assert isinstance(key, APIKey)
    assert now - key.created_date < timedelta(seconds=0.01)
