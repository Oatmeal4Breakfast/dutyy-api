from __future__ import annotations
from typing import TYPE_CHECKING


from src.domain.exceptions import DomainValidationError
from src.domain.user import User, UserUpdateFields, UserSummary
from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger

if TYPE_CHECKING:
    from uuid import UUID

logger = get_logger(__name__)


class UserNotFoundError(Exception):
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__(f"user with id {user_id} not found")


class UserService:
    def __init__(self, uow: AbstractUnitOfWork) -> None:
        self._uow = uow

    async def get_all_users(
        self, page: int = 1, page_size: int = 100
    ) -> list[UserSummary]:
        async with self._uow as uow:
            users: list[UserSummary] = await uow.user.get_all(
                page=page, page_size=page_size
            )
        return users

    async def create_user(self, fname: str, lname: str, email: str) -> UserSummary:
        user = User.create(first_name=fname, last_name=lname, email=email)
        async with self._uow as uow:
            await uow.user.add(user)
            user = user.to_summary()
            await uow.commit()
        logger.info(
            event="user_created", user_id=str(user.id), created=user.created_date
        )
        return user

    async def get_user_by_id(self, user_id: UUID) -> UserSummary:
        async with self._uow as uow:
            user: User | None = await uow.user.get_by_id(user_id=user_id)

            if user is None:
                raise UserNotFoundError(user_id)
        return user.to_summary()

    async def update_user(
        self, user_id: UUID, changes: UserUpdateFields
    ) -> UserSummary:
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
            return user.to_summary()

    async def update_password_hash(self, user_id: UUID, new_hash: str) -> UserSummary:
        async with self._uow as uow:
            user: User | None = await uow.user.get_by_id(user_id)

            if user is None:
                logger.error(event="user_not_found", invalid_id=str(user_id))
                raise UserNotFoundError(user_id)

            user.update_password_hash(new_hash)

            await uow.user.update(user)
            await uow.commit()
            logger.info(event="user_password_hash_updated", user_id=str(user_id))
        return user.to_summary()
