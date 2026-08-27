import hashlib
from typing import Any
from uuid import uuid7
from datetime import datetime, timedelta, UTC

from src.domain.device_auth import DeviceCode, DeviceCodeStatus, CHAR_SET


def make_device_code(**kwargs) -> DeviceCode:
    defaults: dict[str, Any] = {
        "hashed_device_code": "hashed_abc123",
        "user_code": "BCDF-GH2J",
        "status": DeviceCodeStatus.PENDING,
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
    }
    return DeviceCode(**{**defaults, **kwargs})


# --- issue ---


def test_issue_returns_raw_and_device_code() -> None:
    raw, code = DeviceCode.issue(expires_at=None)
    assert isinstance(raw, str)
    assert raw
    assert isinstance(code, DeviceCode)


def test_issue_hash_matches_raw() -> None:
    raw, code = DeviceCode.issue(expires_at=None)
    assert code.hashed_device_code == DeviceCode.hash_device_code(raw)


def test_issue_starts_pending_and_unassigned() -> None:
    _, code = DeviceCode.issue(expires_at=None)
    assert code.status == DeviceCodeStatus.PENDING
    assert code.user_id is None
    assert code.user_code


def test_issue_default_expiry_is_fifteen_minutes() -> None:
    _, code = DeviceCode.issue(expires_at=None)
    expected = datetime.now(UTC) + timedelta(minutes=15)
    assert abs((code.expires_at - expected).total_seconds()) < 1


def test_issue_respects_explicit_expiry() -> None:
    expires = datetime.now(UTC) + timedelta(minutes=5)
    _, code = DeviceCode.issue(expires_at=expires)
    assert code.expires_at == expires


# --- generate_user_code ---


def test_generate_user_code_format() -> None:
    code = DeviceCode.generate_user_code()
    assert len(code) == 9
    assert code[4] == "-"


def test_generate_user_code_uses_charset() -> None:
    code = DeviceCode.generate_user_code()
    assert all(char in CHAR_SET for char in code if char != "-")


def test_generate_user_code_is_unique() -> None:
    assert DeviceCode.generate_user_code() != DeviceCode.generate_user_code()


# --- hash_device_code ---


def test_hash_device_code_is_deterministic() -> None:
    assert DeviceCode.hash_device_code("raw") == DeviceCode.hash_device_code("raw")


def test_hash_device_code_matches_sha256() -> None:
    assert DeviceCode.hash_device_code("raw") == hashlib.sha256(b"raw").hexdigest()


# --- mark_approved ---


def test_mark_approved_sets_status_and_user() -> None:
    user_id = uuid7()
    code = make_device_code()

    assert code.status == DeviceCodeStatus.PENDING
    assert code.user_id is None

    code.mark_approved(user_id)

    assert code.status == DeviceCodeStatus.APPROVED
    assert code.user_id == user_id


# --- is_expired ---


def test_is_expired_true_when_past() -> None:
    code = make_device_code(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert code.is_expired() is True


def test_is_expired_false_when_future() -> None:
    code = make_device_code(expires_at=datetime.now(UTC) + timedelta(minutes=5))
    assert code.is_expired() is False


# --- to_dict ---


def test_to_dict_keys_match_fields() -> None:
    code = make_device_code(user_id=uuid7())
    result = code.to_dict()
    assert set(result.keys()) == {
        "hashed_device_code",
        "user_code",
        "status",
        "expires_at",
        "key_name",
        "key_lifetime",
        "user_id",
    }
