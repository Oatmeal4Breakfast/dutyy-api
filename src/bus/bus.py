from __future__ import annotations

import asyncio
from typing import Protocol, Callable, TYPE_CHECKING, Awaitable

from src.logger import get_logger

if TYPE_CHECKING:
    from src.domain.events import Event

logger = get_logger(__name__)


class EventBusProtocol(Protocol):
    def subscribe[E: Event](
        self, event_type: type[E], handler: Callable[[E], Awaitable]
    ) -> None: ...
    def unsubscribe[E: Event](
        self, event: type[E], handler: Callable[[E], Awaitable]
    ) -> None: ...
    async def publish(self, event: Event) -> None: ...


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[Callable]] = {}

    def subscribe[E: Event](
        self, event_type: type[E], handler: Callable[[E], Awaitable]
    ):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(event="new_event_handler_registered", type=event_type)

    def unsubscribe[E: Event](
        self, event_type: type[E], handler: Callable[[E], Awaitable]
    ) -> None:
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
        logger.info(event="handler_unsubscribed_from_event", event_type=event_type)

    async def publish(self, event: Event) -> None:
        handlers: list[Callable] = self._handlers.get(type(event), []).copy()

        if not handlers:
            logger.warn(event="no_handlers_for_event", event_type=type(event).__name__)
            return

        logger.debug(
            event="publishing_events",
            event_type=type(event).__name__,
            handler_count=len(handlers),
        )

        tasks: list[Awaitable] = [handler(event) for handler in handlers]

        await asyncio.gather(*tasks)
