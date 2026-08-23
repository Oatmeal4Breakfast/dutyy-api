import pytest

from datetime import datetime, timedelta, UTC

from structlog.testing import capture_logs
from sqlalchemy.exc import IntegrityError

from tests.conftest import make_device_auth_service

from src.config import DeviceAuthConfig
from src.domain.exceptions import DeviceCodeCollisionError
from src.service.device_auth_service import (
    DeviceAuthService,
    DeviceCodeClientData,
    DeviceAuthError,
    PollResult,
    PollStatus,
)
from src.domain.device_auth import DeviceCode, DeviceCodeStatus
from src.repository.device_auth_repo import DeviceAuthRepo


class _CollisionUow:
    """Callable stand-in for uow_factory that scripts the outcome of add().

    The real UnitOfWork opens a fresh session per call, so each collision retry
    gets a clean transaction. The DB-backed FakeUnitOfWork reuses one session
    and therefore cannot model "new transaction per attempt" -- so the retry and
    exhaustion paths are exercised against this lightweight double instead.
    """

    def __init__(self, add_effects: list[BaseException | None]) -> None:
        self.add_effects = add_effects
        self.add_calls = 0
        self.commit_calls = 0
        self.device_auth = self

    def __call__(self) -> "_CollisionUow":
        return self

    async def __aenter__(self) -> "_CollisionUow":
        return self

    async def __aexit__(self, *_) -> None:
        return None

    async def add(self, entity) -> None:
        effect = self.add_effects[self.add_calls]
        self.add_calls += 1
        if isinstance(effect, BaseException):
            raise effect

    async def commit(self) -> None:
        self.commit_calls += 1


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT", {}, Exception("duplicate user_code"))


@pytest.mark.integration
class TestDeviceAuthServiceStart:
    async def test_start_issues_and_persists_pending_code(self, session, event_bus):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)

        data = await service.start()

        assert isinstance(data, DeviceCodeClientData)
        assert data.raw_device_code
        assert data.user_code
        assert data.verification_uri == service.verification_uri

        persisted = await repo.get_code_by_hash(
            DeviceCode.hash_device_code(data.raw_device_code)
        )
        assert persisted is not None
        assert persisted.status == DeviceCodeStatus.PENDING
        assert persisted.user_code == data.user_code


class TestDeviceAuthServiceStartRetry:
    async def test_retries_on_collision_then_succeeds(self):
        config = DeviceAuthConfig(
            verification_base_uri="https://dutyy.app/device", max_attempts=3
        )
        uow = _CollisionUow(add_effects=[_integrity_error(), None])
        service = DeviceAuthService(config=config, uow_factory=uow)

        data = await service.start()

        assert isinstance(data, DeviceCodeClientData)
        assert uow.add_calls == 2
        assert uow.commit_calls == 1

    async def test_raises_after_exhausting_attempts(self):
        config = DeviceAuthConfig(
            verification_base_uri="https://dutyy.app/device", max_attempts=3
        )
        uow = _CollisionUow(add_effects=[_integrity_error()] * 3)
        service = DeviceAuthService(config=config, uow_factory=uow)

        with pytest.raises(DeviceCodeCollisionError):
            await service.start()

        assert uow.add_calls == 3
        assert uow.commit_calls == 0


@pytest.mark.integration
class TestDeviceAuthServiceApprove:
    async def test_approve_marks_pending_code_approved(self, session, event_bus, user):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        _, code = DeviceCode.issue()
        await repo.add(code)

        result = await service.approve(user_code=code.user_code, user_id=user.id)

        assert isinstance(result, DeviceCode)
        assert result.status == DeviceCodeStatus.APPROVED
        assert result.user_id == user.id

        persisted = await repo.get_code_by_hash(code.hashed_device_code)
        assert persisted is not None
        assert persisted.status == DeviceCodeStatus.APPROVED
        assert persisted.user_id == user.id

    async def test_approve_unknown_user_code_returns_error(
        self, session, event_bus, user
    ):
        service = make_device_auth_service(session, event_bus)

        with capture_logs() as logs:
            result = await service.approve(user_code="ZZZZ-ZZZZ", user_id=user.id)

        assert isinstance(result, DeviceAuthError)
        assert any(
            log["event"] == "device_code_not_found" and log["log_level"] == "warning"
            for log in logs
        )

    async def test_approve_already_approved_returns_error(
        self, session, event_bus, user
    ):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        _, code = DeviceCode.issue()
        code.mark_approved(user.id)
        await repo.add(code)

        with capture_logs() as logs:
            result = await service.approve(user_code=code.user_code, user_id=user.id)

        assert isinstance(result, DeviceAuthError)
        assert any(
            log["event"] == "device_code_not_eligible_for_approval" for log in logs
        )
        persisted = await repo.get_code_by_hash(code.hashed_device_code)
        assert persisted.status == DeviceCodeStatus.APPROVED

    async def test_approve_expired_code_returns_error(self, session, event_bus, user):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        _, code = DeviceCode.issue(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        await repo.add(code)

        result = await service.approve(user_code=code.user_code, user_id=user.id)

        assert isinstance(result, DeviceAuthError)
        persisted = await repo.get_code_by_hash(code.hashed_device_code)
        assert persisted.status == DeviceCodeStatus.PENDING
        assert persisted.user_id is None


@pytest.mark.integration
class TestDeviceAuthServicePoll:
    async def test_poll_approved_code_returns_user_id_and_consumes(
        self, session, event_bus, user
    ):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        raw, code = DeviceCode.issue()
        code.mark_approved(user.id)
        await repo.add(code)

        result = await service.poll(device_code=raw)

        assert isinstance(result, PollResult)
        assert result.status == PollStatus.APPROVED
        assert result.user_id == user.id

        persisted = await repo.get_code_by_hash(code.hashed_device_code)
        assert persisted.status == DeviceCodeStatus.CONSUMED

    async def test_poll_pending_code_returns_pending(self, session, event_bus):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        raw, code = DeviceCode.issue()
        await repo.add(code)

        result = await service.poll(device_code=raw)

        assert result.status == PollStatus.PENDING
        assert result.user_id is None
        persisted = await repo.get_code_by_hash(code.hashed_device_code)
        assert persisted.status == DeviceCodeStatus.PENDING

    async def test_poll_unknown_device_code_returns_invalid(self, session, event_bus):
        service = make_device_auth_service(session, event_bus)

        result = await service.poll(device_code="not-a-real-device-code")

        assert result.status == PollStatus.INVALID
        assert result.user_id is None

    async def test_poll_expired_approved_code_returns_expired(
        self, session, event_bus, user
    ):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        raw, code = DeviceCode.issue(
            expires_at=datetime.now(UTC) - timedelta(minutes=1)
        )
        code.mark_approved(user.id)
        await repo.add(code)

        result = await service.poll(device_code=raw)

        assert result.status == PollStatus.EXPIRED

    async def test_poll_twice_only_first_consumes(self, session, event_bus, user):
        service = make_device_auth_service(session, event_bus)
        repo = DeviceAuthRepo(session)
        raw, code = DeviceCode.issue()
        code.mark_approved(user.id)
        await repo.add(code)

        first = await service.poll(device_code=raw)
        second = await service.poll(device_code=raw)

        assert first.status == PollStatus.APPROVED
        assert second.status == PollStatus.INVALID
