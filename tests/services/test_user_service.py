import pytest

from unittest.mock import AsyncMock

from src.domain.events import UserCreated
from tests.conftest import make_user_service, FakeUnitOfWork


@pytest.mark.integration
async def test_create_user_fires_event(session, event_bus):
    fake_handler = AsyncMock()
    event_bus.subscribe(UserCreated, fake_handler)
    uow = FakeUnitOfWork(session, event_bus)
    service = make_user_service(uow)

    await service.create_user(fname="test", lname="test", email="test@example.com")

    fake_handler.assert_called_once()
