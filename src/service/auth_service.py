from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from src.config import AuthServiceConfig
from src.db.uow import AbstractUnitOfWork
from src.domain.events import (
    PasswordResetRequested,
    PasswordTokenCreated,
    UserCreated,
)
from src.domain.exceptions import DomainValidationError
from src.domain.token import PasswordSetToken
from src.domain.user import User, UserStatus
from src.logger import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from src.bus.bus import EventBus

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
        self.fake_password: str = auth_service_config.fake_password
        self.fake_password_hash: str = self._hasher.hash(self.fake_password)

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

    async def handle_password_reset(self, user_email: str) -> None:
        async with self._uow_factory() as uow:
            user: User | None = await uow.user.get_active_user_by_email(
                email=user_email
            )

            if user is None:
                return

            existing_tokens: list[
                PasswordSetToken
            ] = await uow.token.get_active_by_user_id(user_id=user.id)

            # invalidate existing_tokens
            for token in existing_tokens:
                token.consume()
                await uow.token.update(token)

            raw_token, token = PasswordSetToken.issue(
                user_id=user.id, ttl=self.token_ttl
            )

            await uow.token.add(token)

            user.events.append(
                PasswordResetRequested(
                    user_id=user.id,
                    user_email=user.email,
                    first_name=user.first_name,
                    raw_token=raw_token,
                )
            )
            logger.info(event="user_password_reset_token_created", user_id=str(user.id))
            await uow.user.update(user)
            await uow.commit()

    async def _authenticate_user(self, user_email: str, password: str) -> User | None:
        async with self._uow_factory() as uow:
            user: User | None = await uow.user.get_active_user_by_email(
                email=user_email
            )

            if user is None:
                logger.warning(event="user_not_found", user_email=user_email)
                await self.verify_hash(self.fake_password, self.fake_password_hash)
                return None

            is_verified: bool = (
                await self.verify_hash(
                    password=password, hashed_password=user.password_hash
                )
                if user.password_hash
                else False
            )

            if not is_verified:
                logger.warning(event="password_incorrect", user_email=user_email)
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
            payload={"sub": str(user.id)}, expires_delta=self.jwt_ttl
        )
        return jwt

    def _subject_from_token(self, token: str) -> UUID | None:
        try:
            payload: dict[str, Any] = jwt.decode(
                jwt=token, key=self.secret, algorithms=[self.algorithm]
            )
        except InvalidTokenError as e:
            logger.warning(event="could_not_decode_token", error=str(e))
            return None

        sub: str | None = payload.get("sub")

        if sub is None:
            logger.error(event="no_user_in_payload")
            return None

        try:
            user_id = UUID(sub)
        except ValueError:
            logger.error("invalid_auth_token", sub=sub)
            return None

        return user_id

    async def get_current_user(self, token: str) -> User | None:
        user_id: UUID | None = self._subject_from_token(token)

        if user_id is None:
            return None

        async with self._uow_factory() as uow:
            user: User | None = await uow.user.get_by_id(user_id=user_id)

        if user is None or user.status != UserStatus.ACTIVE:
            return None

        return user
