from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from src.db.uow import AbstractUnitOfWork
from src.logger import get_logger

if TYPE_CHECKING:
    from src.bus.bus import EventBus
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

logger = get_logger(__name__)


class PublishingService:
    def __init__(
        self,
        uow_factory: Callable[
            [async_sessionmaker[AsyncSession], EventBus], AbstractUnitOfWork
        ],
    ) -> None:
        pass
