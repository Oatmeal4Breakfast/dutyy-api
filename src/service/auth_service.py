from __future__ import annotations
from src.domain.exceptions import DomainValidationError
import jwt
import asyncio
import hashlib

from datetime import timedelta, datetime, UTC
from typing import TYPE_CHECKING
from collections.abc import Callable
from pwdlib import PasswordHash

from src.domain.events import (
    UserCreated,
    PasswordTokenCreated,
)
from src.domain.user import User
from src.domain.token import PasswordSetToken
from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger
from src.config import AuthServiceConfig


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
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
        auth_service_config: AuthServiceConfig,
    ) -> None:
        self._uow_factory: Callable = uow_factory
        self._hasher: PasswordHash = PasswordHash.recommended()
        self.jwt_ttl: timedelta = auth_service_config.jwt_ttl
        self.secret: str = auth_service_config.secret
        self.algorithm: str = auth_service_config.algorithm
        self.token_ttl: timedelta = auth_service_config.token_ttl

    async def set_password(self, raw_token: str, new_password: str) -> None:
        token_hash: str = hashlib.sha256(raw_token.encode()).hexdigest()
        async with self._uow_factory() as uow:
            token: PasswordSetToken | None = await uow.token.get_by_hash(
                token_hash=token_hash
            )
            if token is None:
                logger.error(event="no_password_set_token_found")
                raise DomainValidationError(
                    entity="PasswordSetToken", errors=["PasswordSetToken not found"]
                )

            user: User | None = await uow.user.get_by_id(token.user_id)
            if user is None:
                logger.error(event="user_not_found", user_id=str(token.user_id))
                raise DomainValidationError(
                    "User", errors=[f"user with id {token.user_id} not found"]
                )

            token.consume()

            hashed_password: str = await asyncio.to_thread(
                self._hasher.hash, new_password
            )

            user.update_password_hash(hashed_password)

            await uow.user.update(user)
            await uow.token.update(token)
            await uow.commit()
            logger.info(event="user_password_hash_set", user_id=str(user.id))

    async def verify_hash(self, password: str, hashed_password: str) -> bool:
        return await asyncio.to_thread(self._hasher.verify, password, hashed_password)

    async def handle_user_created(self, event: UserCreated) -> None:
        async with self._uow_factory() as uow:
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

    async def _authenticate_user(self, user_email: str, password: str) -> User | None:
        async with self._uow_factory() as uow:
            user: User | None = await uow.user.get_user_by_email(email=user_email)

            if user is None:
                logger.warn(event="user_not_found", user_email=user_email)
                return None

            is_verified: bool = (
                await self.verify_hash(
                    password=password, hashed_password=user.password_hash
                )
                if user.password_hash
                else False
            )

            if not is_verified:
                logger.warn(event="password_incorrect", user_email=user_email)
                return None

            logger.info(
                event="user_authentication_success",
                user_id=str(user.id),
                user_email=user.email,
            )
            return user

    def _create_access_token(
        self, payload: dict[str, str | datetime], expires_delta: timedelta
    ) -> str:
        to_encode = payload.copy()
        expire: datetime = datetime.now(UTC) + expires_delta
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            payload=to_encode, key=self.secret, algorithm=self.algorithm
        )
        return encoded_jwt

    async def login(self, user_email: str, password: str) -> str | None:
        user: User | None = await self._authenticate_user(
            user_email=user_email, password=password
        )

        if user is None:
            return None

        jwt: str = self._create_access_token(
            payload={"sub": user.email}, expires_delta=self.jwt_ttl
        )
        return jwt
