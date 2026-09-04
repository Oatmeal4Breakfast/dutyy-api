from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum, auto
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import async_object_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Operation(StrEnum):
    GET = auto()
    UPDATE = auto()
    ADD = auto()
    DELETE = auto()


class RepoError(StrEnum):
    DB_UNAVAILABLE = auto()
    INTEGRITY_CONFLICT = auto()


class DetachedEntityError(Exception):
    """Raised when a write is attempted against an entity this session does not manage.

    Writes are emitted by the unit of work rather than by hand-built statements, so an
    entity that is transient or attached to another session would be flushed silently as
    a no-op. Fail loudly instead.
    """

    def __init__(self, entity: str) -> None:
        self.entity = entity
        super().__init__(f"{self.entity} is not managed by this session")


def assert_managed(session: AsyncSession, entity: object) -> None:
    if async_object_session(entity) is not session:
        raise DetachedEntityError(type(entity).__name__)


class AbstractRepository[T, F = T](ABC):
    @abstractmethod
    async def get_all(self) -> list[F]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, entity: T) -> None:
        raise NotImplementedError

    @abstractmethod
    async def add(self, entity: T) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update(self, entity: T) -> None:
        raise NotImplementedError
