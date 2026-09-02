from __future__ import annotations

from typing import TYPE_CHECKING

from src.domain.events import (
    PasswordResetRequested,
    PasswordTokenCreated,
    UserCreated,
)

if TYPE_CHECKING:
    from src.bus.bus import EventBus
    from src.service.auth_service import AuthService
    from src.service.email_service import EmailService


def register_event_handlers(
    bus: EventBus,
    *,
    auth_service: AuthService,
    email_service: EmailService,
) -> None:
    """Central composition root for the event graph.

    Every event -> handler subscription lives here so the full graph is
    readable in one place. Add new subscriptions below as handlers land.
    """
    bus.subscribe(UserCreated, auth_service.handle_user_created)
    bus.subscribe(PasswordTokenCreated, email_service.handle_user_created)
    bus.subscribe(PasswordResetRequested, email_service.handle_password_reset_requested)
