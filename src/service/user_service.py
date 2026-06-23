from __future__ import annotations
from src.domain.exceptions import DomainValidationError
from typing import TYPE_CHECKING


from src.domain.user import User, UserUpdateFields
from src.db.uow import UnitOfWork
from src.logger import get_logger

if TYPE_CHECKING:
    from uuid import UUID

logger = get_logger(__name__)


class UserNotFoundError(Exception):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"user with id {user_id} not found")


class UserService:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    async def create_user(self, fname: str, lname: str, email: str) -> User:
        user = User.create(first_name=fname, last_name=lname, email=email)
        async with self._uow as uow:
            await uow.user.add(user)
            await uow.commit()
        logger.info(
            event="user_created", user_id=str(user.id), created=user.created_date
        )
        return user

    async def update_user(self, user_id: UUID, changes: UserUpdateFields) -> User:
        errors: list[str] = []
        async with self._uow as uow:
            user: User | None = await uow.user.get_by_id(user_id)

            if user is None:
                logger.error(event="user_not_found", invalid_id=str(user_id))
                raise UserNotFoundError(user_id)

            if changes.first_name is not None:
                try:
                    user.update_first_name(changes.first_name)
                except DomainValidationError as e:
                    errors.extend(e.errors)

            if changes.last_name is not None:
                try:
                    user.update_last_name(changes.last_name)
                except DomainValidationError as e:
                    errors.extend(e.errors)

            if changes.email is not None:
                try:
                    user.update_email(changes.email)
                except DomainValidationError as e:
                    errors.extend(e.errors)

            if changes.status is not None:
                try:
                    user.update_status(changes.status)
                except DomainValidationError as e:
                    errors.extend(e.errors)

            if errors:
                logger.error(
                    event="user_update_failed",
                    user_id=str(user_id),
                    err=str(errors),
                )
                raise DomainValidationError("User", errors)

            await uow.user.update(user)
            await uow.commit()
            logger.info(event="user_update_success", user_id=user_id)
            return user

    async def update_password_hash(self, user_id: UUID, new_hash: str) -> User:
        async with self._uow as uow:
            user: User | None = await uow.user.get_by_id(user_id)

            if user is None:
                logger.error(event="user_not_found", invalid_id=str(user_id))
                raise UserNotFoundError(user_id)

            user.update_password_hash(new_hash)

            await uow.user.update(user)
            await uow.commit()
            logger.info(event="user_password_hash_updated", user_id=str(user_id))
            return user
