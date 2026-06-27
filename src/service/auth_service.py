from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING, LiteralString

from pwdlib import PasswordHash

from src.domain.events import (
    UserCreated,
    PasswordHashCreated,
)
from src.domain.user import User
from src.db.uow import UnitOfWork
from src.logger import get_logger


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from src.bus.bus import EventBus

logger = get_logger(__name__)

# TODO: Emit an event so that we can fire the email off to the user
# TODO: Persist the password hash to the user needing it.
# TODO: Write tests for this service
# TODO: Write a depdency getter for this class for injection into routes
# TODO: Implement Oauth2 with OauthPasswordBearer


class AuthService:
    def __init__(
        self, session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus
    ) -> None:
        self._uow = UnitOfWork(session_factory, event_bus)
        self._valid_characters: LiteralString = (
            string.ascii_letters + string.digits + string.punctuation
        )
        self._password_hash: PasswordHash = PasswordHash.recommended()

    def _generate_random_password(self) -> str:
        return "".join(secrets.choice(self._valid_characters) for _ in range(12))

    def _hash_password(self, plain_password: str) -> str:
        return self._password_hash.hash(password=plain_password)

    async def handle_user_created(self, event: UserCreated) -> None:
        plain_password: str = self._generate_random_password()
        hashed_password: str = self._hash_password(plain_password)

        async with self._uow as uow:
            user: User | None = await uow.user.get_by_id(event.user_id)

            if user is None:
                return

            user.update_password_hash(password_hash=hashed_password)
            user.events.append(
                PasswordHashCreated(
                    user_id=user.id,
                    user_email=user.email,
                    plain_text_password=plain_password,
                )
            )
            logger.info(event="user_password_hash_created", user_id=str(user.id))
            await uow.user.update(user)
            await uow.commit()
