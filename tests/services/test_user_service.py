import pytest

from unittest.mock import AsyncMock

from src.domain.events import UserCreated, UserStatusChanged
from src.domain.user import UserStatus, UserUpdateFields
from tests.conftest import make_user_service


@pytest.mark.integration
class TestUserService:
    async def test_create_user_fires_event(self, session, event_bus):
        fake_handler = AsyncMock()
        event_bus.subscribe(UserCreated, fake_handler)
        service = make_user_service(session, event_bus)

        await service.create_user(fname="test", lname="test", email="test@example.com")

        fake_handler.assert_called_once()

    async def test_update_user_fires_events(self, user, session, event_bus):
        fake_user_status_handler = AsyncMock()

        event_bus.subscribe(UserStatusChanged, fake_user_status_handler)

        service = make_user_service(session, event_bus)

        changes = UserUpdateFields(status=UserStatus.INACTIVE)

        await service.update_user(user_id=user.id, changes=changes)

        fake_user_status_handler.assert_called_once()
