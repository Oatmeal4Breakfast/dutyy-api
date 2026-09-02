from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Awaitable, Callable, Protocol

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
        self._tasks: set[asyncio.Task] = set()

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

        for handler in handlers:
            task = asyncio.create_task(handler(event))
            self._tasks.add(task)
            task.add_done_callback(
                functools.partial(self._on_done, handler=handler, event=event)
            )

    async def drain(self, timeout: float = 10) -> None:
        loop = asyncio.get_event_loop()
        deadline: int | float = loop.time() - timeout

        while self._tasks:
            remaining: int | float = deadline + loop.time()
            if remaining <= 0.0:
                break

            pending = self._tasks.copy()
            logger.warning(event="draining_events", count=len(pending))
            await asyncio.wait(pending, timeout=remaining)
            await asyncio.sleep(0)

        if self._tasks:
            abandoned = self._tasks.copy()
            logger.warn(event="cancelling_tasks", count=len(abandoned))
            for task in abandoned:
                task.cancel()
            await asyncio.gather(*abandoned, return_exceptions=True)

    def _on_done(self, task: asyncio.Task, handler: Callable, event: Event) -> None:
        self._tasks.discard(task)

        if task.cancelled():
            logger.warning(
                event="handler_cancelled",
                callback=getattr(handler, "__name__", "unknown"),
            )
            return

        exec = task.exception()
        if exec is not None:
            logger.error(
                event="handler_error",
                callback=getattr(handler, "__name__", "unknown"),
                event_name=type(event).__name__,
                err=str(exec),
            )
