from __future__ import annotations
import resend
from typing import cast

from src.domain.events import PasswordHashCreated
from src.config import EmailServiceConfig
from src.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    def __init__(self, email_service_config: EmailServiceConfig, frontend_url: str):
        resend.api_key: str = email_service_config.resend_api_key
        if not resend.api_key:
            raise ValueError("resend_api_key is not set")
        self.from_addr: str = email_service_config.sender_email

    def build_welcome_email(self, user_name: str, temporary_password: str) -> str:
        return f"""
            <p>Hi {user_name},</p>
            <p>Welcome to dutyy! Your account has been created.</p>
            <p>Temporary password: {temporary_password}</p>
        """

    async def send_welcome_email(self, event: PasswordHashCreated):
        html: str = self.build_welcome_email(
            user_name=event.first_name,
            temporary_password=event.plain_text_password,
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
        email = await resend.Emails.send_async(payload)
        logger.debug(event="sending_welcome_email", response=email)
        return email
