from __future__ import annotations

from typing import TYPE_CHECKING, Callable
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger

if TYPE_CHECKING:
    from src.bus.bus import EventBus

logger = get_logger(__name__)


class APIKeyService:
    def __init__(
        self,
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
    ) -> None:
        self._uow_factory: Callable = uow_factory
