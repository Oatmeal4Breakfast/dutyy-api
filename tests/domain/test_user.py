from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.domain.exceptions import DomainValidationError
from src.domain.user import User, UserStatus


def make_user(**kwargs) -> User:
    defaults: dict[str, Any] = {
        "first_name": "john",
        "last_name": "doe",
        "email": "john.doe@example.com",
    }
    return User(**{**defaults, **kwargs})


def test_create_user_success() -> None:
    user = make_user()

    time_diff = datetime.now(UTC) - user.created_date
    assert time_diff < timedelta(seconds=1)
    assert isinstance(user, User)
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.status == UserStatus.ACTIVE


def test_create_user_normalizes_name() -> None:
    user = make_user(first_name="  john  ", last_name="  doe  ")
    assert user.first_name == "John"
    assert user.last_name == "Doe"


def test_create_user_normalizes_email() -> None:
    user = make_user(email="John.Doe@Example.COM")
    assert user.email == "John.Doe@example.com"


def test_create_user_empty_first_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_user(first_name="")


def test_create_user_whitespace_first_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_user(first_name="   ")


def test_create_user_empty_last_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_user(last_name="")


def test_create_user_whitespace_last_name_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_user(last_name="   ")


def test_create_user_invalid_email_fails() -> None:
    with pytest.raises(DomainValidationError):
        make_user(email="not-an-email")


def test_full_name() -> None:
    user = make_user()
    assert user.full_name == "John Doe"


def test_update_first_name_success() -> None:
    user = make_user()
    user.update_first_name("  jane  ")

    assert user.first_name == "Jane"
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)


def test_update_first_name_empty_fails() -> None:
    user = make_user()
    with pytest.raises(DomainValidationError):
        user.update_first_name("")


def test_update_first_name_whitespace_fails() -> None:
    user = make_user()
    with pytest.raises(DomainValidationError):
        user.update_first_name("   ")


def test_update_last_name_success() -> None:
    user = make_user()
    user.update_last_name("  smith  ")

    assert user.last_name == "Smith"
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)


def test_update_last_name_empty_fails() -> None:
    user = make_user()
    with pytest.raises(DomainValidationError):
        user.update_last_name("")


def test_update_last_name_whitespace_fails() -> None:
    user = make_user()
    with pytest.raises(DomainValidationError):
        user.update_last_name("   ")


def test_update_email_success() -> None:
    user = make_user()
    user.update_email("jane.doe@example.com")

    assert user.email == "jane.doe@example.com"
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)


def test_update_email_idempotent() -> None:
    user = make_user()
    user.update_email("john.doe@example.com")

    assert user.modified_date is None


def test_update_email_invalid_fails() -> None:
    user = make_user()
    with pytest.raises(DomainValidationError):
        user.update_email("not-an-email")


def test_update_status_idempotent() -> None:
    user = make_user()
    user.update_status(UserStatus.ACTIVE)

    assert user.modified_date is None


def test_update_status_to_inactive() -> None:
    user = make_user()
    user.update_status(UserStatus.INACTIVE)

    assert user.status == UserStatus.INACTIVE
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)


def test_update_status_to_blocked() -> None:
    user = make_user()
    user.update_status(UserStatus.BLOCKED)

    assert user.status == UserStatus.BLOCKED
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)


def test_update_status_reversible() -> None:
    user = make_user()
    user.update_status(UserStatus.INACTIVE)

    assert user.status == UserStatus.INACTIVE

    user.update_status(UserStatus.ACTIVE)

    assert user.status == UserStatus.ACTIVE


def test_update_password_hash_success() -> None:
    user = make_user()

    assert user.password_hash is None

    user.update_password_hash("hashed_value_abc123")

    assert user.password_hash == "hashed_value_abc123"
    assert user.modified_date is not None

    time_diff = datetime.now(UTC) - user.modified_date
    assert time_diff < timedelta(seconds=1)
