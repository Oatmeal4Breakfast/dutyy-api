from __future__ import annotations
import jwt

from datetime import timedelta, datetime, UTC
from typing import TYPE_CHECKING
from pwdlib import PasswordHash

from src.domain.events import (
    UserCreated,
    PasswordTokenCreated,
)
from src.domain.user import User
from src.domain.token import PasswordSetToken
from src.db.uow import UnitOfWork
from src.logger import get_logger
from src.config import AuthServiceConfig
from src.service.user_service import UserNotFoundError


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from src.bus.bus import EventBus
    from uuid import UUID

logger = get_logger(__name__)


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
        self._hasher: PasswordHash = PasswordHash.recommended()
        self.jwt_ttl: timedelta = auth_service_config.jwt_ttl
        self.secret: str = auth_service_config.secret
        self.algorithm: str = auth_service_config.algorithm
        self.token_ttl: timedelta = auth_service_config.token_ttl

    # -----------------Use for password hashing only---------------------------
    def _hash(self, raw: str) -> str:
        return self._hasher.hash(raw.encode())

    def verify_hash(self, password: str, hashed_password: str) -> bool:
        return self._hasher.verify(password, hashed_password)

    # ------------------------------------------------------------------------

    async def handle_user_created(self, event: UserCreated) -> None:
        async with UnitOfWork(self._session, self._bus) as uow:
            user: User | None = await uow.user.get_by_id(event.user_id)

            if user is None:
                return

            raw_token, token = PasswordSetToken.issue(
                user_id=user.id, ttl=self.token_ttl
            )
            await uow.token.add(token)
            user.events.append(
                PasswordTokenCreated(
                    user_id=user.id,
                    first_name=user.first_name,
                    user_email=user.email,
                    raw_token=raw_token,
                )
            )
            logger.info(event="user_password_hash_created", user_id=str(user.id))
            await uow.user.update(user)
            await uow.commit()

    async def authenticate_user(
        self, user_email: str, user_password: str
    ) -> tuple[User, bool]:
        async with UnitOfWork(self._session, self._bus) as uow:
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
