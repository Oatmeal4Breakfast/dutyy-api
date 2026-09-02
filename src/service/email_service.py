from __future__ import annotations

from typing import cast

import resend

from src.config import EmailServiceConfig
from src.domain.events import PasswordResetRequested, PasswordTokenCreated
from src.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    def __init__(self, email_service_config: EmailServiceConfig, frontend_url: str):
        resend.api_key: str = email_service_config.resend_api_key
        if not resend.api_key:
            raise ValueError("resend_api_key is not set")
        self.from_addr: str = email_service_config.sender_email
        self.frontend_url: str = frontend_url

    def _build_welcome_email(self, user_name: str, raw_token: str) -> str:
        link: str = f"{self.frontend_url}/set-password?token={raw_token}"
        return f"""
            <p>Hi {user_name},</p>
            <p>Welcome to dutyy! Your account has been created.</p>
            <p>Click <a href={link}>here</a> to set your password</p>
        """

    def _build_password_reset_email(self, user_name: str, raw_token: str) -> str:
        link: str = f"{self.frontend_url}/set-password?token={raw_token}"
        return f"""
            <p>Hi {user_name},</p>
            <p>A password reset has been requested. Your link is below.</p>
            <p>Click <a href={link}>here</a> to set your password</p>
            """

    async def handle_user_created(self, event: PasswordTokenCreated):
        html: str = self._build_welcome_email(
            user_name=event.first_name,
            raw_token=event.raw_token,
        )

        payload = cast(
            resend.Emails.SendParams,
            {
                "from": self.from_addr,
                "to": event.user_email,
                "subject": "Welcome to Dutyy",
                "html": html,
            },
        )

        send_options = cast(
            resend.Emails.SendOptions,
            {"idempotency_key": f"set-password/{event.raw_token}"},
        )
        email = await resend.Emails.send_async(params=payload, options=send_options)
        logger.debug(event="sending_welcome_email", response=email)
        return email

    async def handle_password_reset_requested(self, event: PasswordResetRequested):
        html: str = self._build_password_reset_email(
            user_name=event.first_name, raw_token=event.raw_token
        )

        payload = cast(
            resend.Emails.SendParams,
            {
                "from": self.from_addr,
                "to": event.user_email,
                "subject": "Dutyy - Password Reset",
                "html": html,
            },
        )

        send_options = cast(
            resend.Emails.SendOptions,
            {"idempotency_key": f"set-password/{event.raw_token}"},
        )

        email = await resend.Emails.send_async(params=payload, options=send_options)
        logger.info(event="sending_password_reset_email", response=email)
        return email
