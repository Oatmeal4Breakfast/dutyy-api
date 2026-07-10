from __future__ import annotations
import resend
from typing import cast

from src.domain.events import PasswordTokenCreated
from src.config import EmailServiceConfig
from src.logger import get_logger

logger = get_logger(__name__)


class EmailService:
    def __init__(self, email_service_config: EmailServiceConfig, frontend_url: str):
        resend.api_key: str = email_service_config.resend_api_key
        if not resend.api_key:
            raise ValueError("resend_api_key is not set")
        self.from_addr: str = email_service_config.sender_email
        self.frontend_url: str = frontend_url

    def build_welcome_email(self, user_name: str, raw_token: str) -> str:
        link: str = self.frontend_url + raw_token
        return f"""
            <p>Hi {user_name},</p>
            <p>Welcome to dutyy! Your account has been created.</p>
            <p>Click <a href={link}>here</a> to set your password</p>
        """
        logger.info(event="welcome_email_built", token=raw_token)

    async def send_welcome_email(self, event: PasswordTokenCreated):
        html: str = self.build_welcome_email(
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
        email = await resend.Emails.send_async(payload)
        logger.debug(event="sending_welcome_email", response=email)
        return email
