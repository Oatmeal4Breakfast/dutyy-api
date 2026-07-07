from abc import ABC, abstractmethod
from enum import StrEnum, auto


class Operation(StrEnum):
    GET = auto()
    UPDATE = auto()
    ADD = auto()
    DELETE = auto()


class RepoError(StrEnum):
    DB_UNAVAILABLE = auto()
    INTEGRITY_CONFLICT = auto()


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
