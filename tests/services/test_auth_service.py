import pytest
import jwt

from uuid import uuid7
from datetime import timedelta
from unittest.mock import AsyncMock

from pwdlib import PasswordHash

from tests.conftest import make_auth_service

from src.domain.events import UserCreated, PasswordTokenCreated
from src.domain.token import PasswordSetToken
from src.domain.user import User, UserStatus
from src.domain.exceptions import DomainValidationError
from src.repository.token_repo import PasswordSetTokenRepo
from src.repository.user_repo import UserRepo


_hasher = PasswordHash.recommended()


@pytest.mark.integration
class TestAuthService:
    async def test_handle_user_created_fires_event(self, session, event_bus, user):
        fake_handler = AsyncMock()
        event_bus.subscribe(PasswordTokenCreated, fake_handler)

        event = UserCreated(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_date=user.created_date,
        )

        auth_service = make_auth_service(session, event_bus)

        await auth_service.handle_user_created(event)

        fake_handler.assert_called_once()

    async def test_set_password_hashes_and_consumes_token(
        self, session, event_bus, user
    ):
        user_id = user.id
        raw_token, token = PasswordSetToken.issue(
            user_id=user_id, ttl=timedelta(minutes=30)
        )
        token_hash = token.token_hash
        await PasswordSetTokenRepo(session).add(token)

        auth_service = make_auth_service(session, event_bus)

        await auth_service.set_password(raw_token, "s3cret-pass")

        reloaded = await UserRepo(session).get_by_id(user_id)
        assert reloaded is not None
        assert reloaded.password_hash is not None
        assert await auth_service.verify_hash("s3cret-pass", reloaded.password_hash)

        consumed = await PasswordSetTokenRepo(session).get_by_hash(
            token_hash=token_hash
        )
        assert consumed is not None
        assert consumed.is_used()

    async def test_set_password_unknown_token_raises(self, session, event_bus):
        auth_service = make_auth_service(session, event_bus)

        with pytest.raises(DomainValidationError):
            await auth_service.set_password("does-not-exist", "whatever")

    async def test_set_password_expired_token_raises(self, session, event_bus, user):
        raw_token, token = PasswordSetToken.issue(
            user_id=user.id, ttl=timedelta(minutes=-1)
        )
        await PasswordSetTokenRepo(session).add(token)

        auth_service = make_auth_service(session, event_bus)

        with pytest.raises(DomainValidationError):
            await auth_service.set_password(raw_token, "s3cret-pass")

    async def test_set_password_already_used_token_raises(
        self, session, event_bus, user
    ):
        raw_token, token = PasswordSetToken.issue(
            user_id=user.id, ttl=timedelta(minutes=30)
        )
        token.consume()
        await PasswordSetTokenRepo(session).add(token)

        auth_service = make_auth_service(session, event_bus)

        with pytest.raises(DomainValidationError):
            await auth_service.set_password(raw_token, "s3cret-pass")

    async def test_authenticate_user_valid_credentials(self, session, event_bus, user):
        user.update_password_hash(_hasher.hash("correct-horse"))
        await UserRepo(session).update(user)

        auth_service = make_auth_service(session, event_bus)

        result = await auth_service._authenticate_user(user.email, "correct-horse")

        assert result is not None
        assert result.id == user.id

    async def test_authenticate_user_wrong_password_returns_none(
        self, session, event_bus, user
    ):
        user.update_password_hash(_hasher.hash("correct-horse"))
        await UserRepo(session).update(user)

        auth_service = make_auth_service(session, event_bus)

        result = await auth_service._authenticate_user(user.email, "wrong-password")

        assert result is None

    async def test_login_token_roundtrip(self, session, event_bus, user):
        user.update_password_hash(_hasher.hash("correct-horse"))
        await UserRepo(session).update(user)
        auth_service = make_auth_service(session, event_bus)

        token: str | None = await auth_service.login(
            user_email=user.email, password="correct-horse"
        )
        assert token is not None

        current: User | None = await auth_service.get_current_user(token)
        assert current is not None
        assert current.id == user.id

    async def test_get_current_user_rejects_user_blocked_after_login(
        self, session, event_bus, user
    ):
        user.update_password_hash(_hasher.hash("correct-horse"))
        await UserRepo(session).update(user)

        auth_service = make_auth_service(session, event_bus)

        token: str | None = await auth_service.login(
            user_email=user.email, password="correct-horse"
        )
        assert token is not None

        user.update_status(status=UserStatus.BLOCKED)
        await UserRepo(session).update(user)

        result: User | None = await auth_service.get_current_user(token)

        assert result is None

    async def test_login_blocked_user_returns_none(self, session, event_bus, user):
        user.update_password_hash(_hasher.hash("correct-horse"))
        user.update_status(status=UserStatus.BLOCKED)
        await UserRepo(session).update(user)

        auth_service = make_auth_service(session, event_bus)

        token: str | None = await auth_service.login(
            user_email=user.email, password="correct-horse"
        )

        assert token is None

    async def test_authenticate_user_unknown_email_returns_none(
        self, session, event_bus
    ):
        auth_service = make_auth_service(session, event_bus)

        result = await auth_service._authenticate_user(
            "nobody@example.com", "whatever"
        )

        assert result is None

    async def test_authenticate_user_without_password_hash_returns_none(
        self, session, event_bus, user
    ):
        auth_service = make_auth_service(session, event_bus)

        result = await auth_service._authenticate_user(user.email, "anything")

        assert result is None

    async def test_get_current_user_malformed_token_returns_none(
        self, session, event_bus
    ):
        auth_service = make_auth_service(session, event_bus)

        result = await auth_service.get_current_user("not-a-jwt")

        assert result is None

    async def test_get_current_user_wrong_signature_returns_none(
        self, session, event_bus, user
    ):
        forged = jwt.encode(
            {"sub": str(user.id)}, key="attacker-secret", algorithm="HS256"
        )
        auth_service = make_auth_service(session, event_bus)

        result = await auth_service.get_current_user(forged)

        assert result is None

    async def test_get_current_user_expired_token_returns_none(
        self, session, event_bus, user
    ):
        auth_service = make_auth_service(session, event_bus)
        expired = auth_service._create_access_token(
            payload={"sub": str(user.id)}, expires_delta=timedelta(minutes=-1)
        )

        result = await auth_service.get_current_user(expired)

        assert result is None

    async def test_get_current_user_missing_sub_returns_none(
        self, session, event_bus
    ):
        auth_service = make_auth_service(session, event_bus)
        token = auth_service._create_access_token(
            payload={}, expires_delta=timedelta(minutes=5)
        )

        result = await auth_service.get_current_user(token)

        assert result is None

    async def test_get_current_user_non_uuid_sub_returns_none(
        self, session, event_bus
    ):
        auth_service = make_auth_service(session, event_bus)
        token = auth_service._create_access_token(
            payload={"sub": "not-a-uuid"}, expires_delta=timedelta(minutes=5)
        )

        result = await auth_service.get_current_user(token)

        assert result is None

    async def test_get_current_user_unknown_user_returns_none(
        self, session, event_bus
    ):
        auth_service = make_auth_service(session, event_bus)
        token = auth_service._create_access_token(
            payload={"sub": str(uuid7())}, expires_delta=timedelta(minutes=5)
        )

        result = await auth_service.get_current_user(token)

        assert result is None
