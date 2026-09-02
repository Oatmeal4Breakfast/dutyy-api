from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.repository.device_auth_repo import DeviceAuthRepo


def make_device_code(**kwargs: Any) -> DeviceCode:
    defaults: dict[str, Any] = {
        "hashed_device_code": "hash_default",
        "user_code": "BCDF-GH2J",
        "status": DeviceCodeStatus.PENDING,
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
        "user_id": None,
    }
    return DeviceCode(**{**defaults, **kwargs})


@pytest.mark.integration
class TestDeviceAuthRepo:
    async def test_add_and_get_by_hash(self, session):
        repo = DeviceAuthRepo(session)
        await repo.add(make_device_code(hashed_device_code="hash_abc"))

        result = await repo.get_code_by_hash("hash_abc")

        assert isinstance(result, DeviceCode)
        assert result.hashed_device_code == "hash_abc"
        assert result.status == DeviceCodeStatus.PENDING

    async def test_get_by_hash_not_found(self, session):
        repo = DeviceAuthRepo(session)
        assert await repo.get_code_by_hash("does_not_exist") is None

    async def test_get_by_user_code(self, session):
        repo = DeviceAuthRepo(session)
        await repo.add(make_device_code(hashed_device_code="h1", user_code="AAAA-BBBB"))

        result = await repo.get_code_by_user_code("AAAA-BBBB")

        assert isinstance(result, DeviceCode)
        assert result.user_code == "AAAA-BBBB"

    async def test_get_by_user_code_not_found(self, session):
        repo = DeviceAuthRepo(session)
        assert await repo.get_code_by_user_code("ZZZZ-ZZZZ") is None

    async def test_update_persists_approval(self, session, user):
        repo = DeviceAuthRepo(session)
        code = make_device_code(hashed_device_code="h_upd")
        await repo.add(code)

        code.mark_approved(user.id)
        await repo.update(code)

        result = await repo.get_code_by_hash("h_upd")
        assert result.status == DeviceCodeStatus.APPROVED
        assert result.user_id == user.id

    # --- consume: the atomic APPROVED -> CONSUMED gate ---

    async def test_consume_approved_returns_row_and_marks_consumed(self, session, user):
        repo = DeviceAuthRepo(session)
        await repo.add(
            make_device_code(
                hashed_device_code="h_con",
                status=DeviceCodeStatus.APPROVED,
                user_id=user.id,
            )
        )

        result = await repo.consume("h_con")

        assert isinstance(result, DeviceCode)
        assert result.status == DeviceCodeStatus.CONSUMED
        assert result.user_id == user.id
        refetched = await repo.get_code_by_hash("h_con")
        assert refetched.status == DeviceCodeStatus.CONSUMED

    async def test_consume_pending_returns_none(self, session):
        repo = DeviceAuthRepo(session)
        await repo.add(make_device_code(hashed_device_code="h_pend"))

        assert await repo.consume("h_pend") is None
        still = await repo.get_code_by_hash("h_pend")
        assert still.status == DeviceCodeStatus.PENDING

    async def test_consume_expired_returns_none(self, session, user):
        repo = DeviceAuthRepo(session)
        await repo.add(
            make_device_code(
                hashed_device_code="h_exp",
                status=DeviceCodeStatus.APPROVED,
                user_id=user.id,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )

        assert await repo.consume("h_exp") is None

    async def test_consume_twice_only_first_wins(self, session, user):
        repo = DeviceAuthRepo(session)
        await repo.add(
            make_device_code(
                hashed_device_code="h_twice",
                status=DeviceCodeStatus.APPROVED,
                user_id=user.id,
            )
        )

        first = await repo.consume("h_twice")
        second = await repo.consume("h_twice")

        assert first is not None
        assert second is None

    # --- purge ---

    async def test_purge_removes_consumed_and_expired_keeps_fresh(self, session, user):
        repo = DeviceAuthRepo(session)
        await repo.add(
            make_device_code(
                hashed_device_code="h_consumed",
                user_code="C1C1-C1C1",
                status=DeviceCodeStatus.CONSUMED,
                user_id=user.id,
            )
        )
        await repo.add(
            make_device_code(
                hashed_device_code="h_expired",
                user_code="E1E1-E1E1",
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await repo.add(
            make_device_code(hashed_device_code="h_fresh", user_code="F1F1-F1F1")
        )

        deleted = await repo.purge()

        assert deleted == 2
        assert await repo.get_code_by_hash("h_fresh") is not None
        assert await repo.get_code_by_hash("h_consumed") is None
        assert await repo.get_code_by_hash("h_expired") is None
