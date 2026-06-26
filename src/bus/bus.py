from __future__ import annotations

import asyncio
from typing import Protocol, Callable, Coroutine, TYPE_CHECKING, Any

from src.logger import get_logger

if TYPE_CHECKING:
    from src.domain.events import Event

logger = get_logger(__name__)

type EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


class EventBusProtocol(Protocol):
    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None: ...
    def unsubscribe(self, event: type[Event], handler: EventHandler) -> None: ...
    async def publish(self, event: Event) -> None: ...


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = {}

    def subscribe(self, event_type: type[Event]):
        def decorator(func):
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func

        logger.info(event="new_event_handler_registered", type=event_type)
        return decorator

    def unsubscribe(self, event: Event, handler: EventHandler) -> None:
        if event in self._handlers and handler in self._handlers[type(event)]:
            self._handlers[type(event)].remove(handler)
        logger.info(
            event="handler_unsubscribed_from_event", event_type=type(event).__name__
        )

    async def publish(self, event: Event) -> None:
        handlers: list[EventHandler] = self._handlers.get(type(event), []).copy()

        if not handlers:
            logger.warn(event="no_handlers_for_event", event_type=type(event).__name__)
            return

        logger.debug(
            event="publishing_events",
            event_type=type(event).__name__,
            handler_count=len(handlers),
        )

        tasks: list[Coroutine[Any, Any, None]] = [
            handler(event) for handler in handlers
        ]

        await asyncio.gather(*tasks)
