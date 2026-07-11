import pytest

from datetime import timedelta
from unittest.mock import AsyncMock

from pwdlib import PasswordHash

from tests.conftest import make_auth_service

from src.domain.events import UserCreated, PasswordTokenCreated
from src.domain.token import PasswordSetToken
from src.domain.exceptions import DomainValidationError
from src.repository.token_repo import PasswordSetTokenRepo
from src.repository.user_repo import UserRepo
from src.service.user_service import UserNotFoundError


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

        result = await auth_service.authenticate_user(user.email, "correct-horse")

        assert result is not None
        assert result.id == user.id

    async def test_authenticate_user_wrong_password_returns_none(
        self, session, event_bus, user
    ):
        user.update_password_hash(_hasher.hash("correct-horse"))
        await UserRepo(session).update(user)

        auth_service = make_auth_service(session, event_bus)

        result = await auth_service.authenticate_user(user.email, "wrong-password")

        assert result is None

    async def test_authenticate_user_unknown_email_raises(self, session, event_bus):
        auth_service = make_auth_service(session, event_bus)

        with pytest.raises(UserNotFoundError):
            await auth_service.authenticate_user("nobody@example.com", "whatever")
