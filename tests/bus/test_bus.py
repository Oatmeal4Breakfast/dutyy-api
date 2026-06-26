from dataclasses import dataclass
from unittest.mock import AsyncMock

from src.bus.bus import EventBus
from src.domain.events import Event


@dataclass(frozen=True)
class FakeEvent(Event):
    pass


async def fake_handler(event: Event):
    print("Hello, World!")


def test_subscribe_to_empty_bus_success():
    bus = EventBus()
    assert len(bus._handlers) == 0
    bus.subscribe(FakeEvent, fake_handler)
    assert len(bus._handlers[FakeEvent]) == 1


def test_subscribe_to_bus_success():
    bus = EventBus()
    bus.subscribe(FakeEvent, fake_handler)

    async def another_fake_handler(event: Event):
        print("Dang, Dude")

    assert len(bus._handlers[FakeEvent]) == 1

    bus.subscribe(FakeEvent, another_fake_handler)

    assert len(bus._handlers[FakeEvent]) == 2


def test_unsubscribe_from_bus_success():
    bus = EventBus()
    bus.subscribe(FakeEvent, fake_handler)
    assert len(bus._handlers[FakeEvent]) == 1

    bus.unsubscribe(FakeEvent, fake_handler)

    assert len(bus._handlers[FakeEvent]) == 0


async def test_publish_event():
    bus = EventBus()
    handler = AsyncMock()

    bus.subscribe(FakeEvent, handler)

    await bus.publish(FakeEvent())

    handler.assert_called_once()
