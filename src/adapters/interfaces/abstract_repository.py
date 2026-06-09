from abc import ABC, abstractmethod


class AbstractRepository[T](ABC):
    @abstractmethod
    async def get_all(self) -> list[T]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def add(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update(self) -> None:
        raise NotImplementedError
