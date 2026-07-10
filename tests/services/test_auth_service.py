import pytest

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from tests.conftest import (
    make_auth_service,
)

from src.domain.events import UserCreated, PasswordTokenCreated

if TYPE_CHECKING:
    pass


@pytest.mark.integration
class TestAuthService:
    async def test_handle_user_created_fires_event(self, session, event_bus, user):
        fake_handler = AsyncMock()
        event_bus.subscribe(PasswordTokenCreated, fake_handler)

        event = UserCreated(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            created_date=user.created_date,
        )

        auth_service = make_auth_service(session, event_bus)

        await auth_service.handle_user_created(event)

        fake_handler.assert_called_once()
