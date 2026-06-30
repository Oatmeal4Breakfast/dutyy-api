from __future__ import annotations
import jwt

import secrets
import string
from datetime import timedelta, datetime, UTC
from typing import TYPE_CHECKING, LiteralString
from pwdlib import PasswordHash

from src.domain.events import (
    UserCreated,
    PasswordHashCreated,
)
from src.domain.user import User
from src.db.uow import UnitOfWork
from src.logger import get_logger
from src.config import AuthServiceConfig
from src.service.user_service import UserNotFoundError


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from src.bus.bus import EventBus
    from uuid import UUID

logger = get_logger(__name__)

# TODO: Emit an event so that we can fire the email off to the user
# TODO: Persist the password hash to the user needing it.
# TODO: Write tests for this service
# TODO: Write a depdency getter for this class for injection into routes
# TODO: Implement Oauth2 with OauthPasswordBearer


class AuthenticationFailed(Exception):
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        super().__init__(f"user with id {user_id} has no password saved")


class AuthService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        auth_service_config: AuthServiceConfig,
    ) -> None:
        self._session: async_sessionmaker[AsyncSession] = session_factory
        self._bus: EventBus = event_bus
        self._valid_characters: LiteralString = (
            string.ascii_letters + string.digits + string.punctuation
        )
        self._password_hash: PasswordHash = PasswordHash.recommended()
        self.expire_time: timedelta = auth_service_config.expire_time
        self.secret: str = auth_service_config.secret
        self.algorithm: str = auth_service_config.algorithm

    def _generate_random_password(self) -> str:
        return "".join(secrets.choice(self._valid_characters) for _ in range(12))

    def _hash_password(self, plain_password: str) -> str:
        return self._password_hash.hash(password=plain_password)

    def verify_hash(self, password: str, hashed_password: str) -> bool:
        return self._password_hash.verify(password, hashed_password)

    async def handle_user_created(self, event: UserCreated) -> None:
        plain_password: str = self._generate_random_password()
        hashed_password: str = self._hash_password(plain_password)

        async with UnitOfWork(self._session, self._bus) as uow:
            user: User | None = await uow.user.get_by_id(event.user_id)

            if user is None:
                return

            user.update_password_hash(password_hash=hashed_password)
            user.events.append(
                PasswordHashCreated(
                    user_id=user.id,
                    first_name=user.first_name,
                    user_email=user.email,
                    plain_text_password=plain_password,
                )
            )
            logger.info(event="user_password_hash_created", user_id=str(user.id))
            await uow.user.update(user)
            await uow.commit()

    async def authenticate_user(
        self, user_email: str, user_password: str
    ) -> tuple[User, bool]:
        async with self._uow as uow:
            user: User | None = await uow.user.get_user_by_email(email=user_email)

            if user is None:
                logger.error(event="user_not_found", user_email=user_email)
                raise UserNotFoundError(user_email)

            if user.password_hash is None:
                logger.error(event="authentication_failed", user_id=str(user.id))
                raise AuthenticationFailed(user_id=user.id)

            is_verified: bool = self.verify_hash(
                password=user_password, hashed_password=user.password_hash
            )

            if is_verified:
                logger.info(
                    event="user_authenticated",
                    user_id=str(user.id),
                    user_email=user.email,
                )
                return user, True
            logger.warn(
                event="user_authentication_failed",
                user_id=str(user.id),
                user_email=user.email,
            )
            return user, False

    def create_access_token(
        self, payload: dict[str, str | datetime], expires_delta: timedelta
    ) -> str:
        to_encode = payload.copy()
        expire: datetime = datetime.now(UTC) + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            payload=to_encode, key=self.secret, algorithm=self.algorithm
        )
        return encoded_jwt
