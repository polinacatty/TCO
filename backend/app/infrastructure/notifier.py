"""Password-reset delivery adapters."""

from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class PasswordResetNotifier(Protocol):
    async def send_reset_token(self, email: str, token: str) -> None: ...


@dataclass(slots=True)
class LoggingPasswordResetNotifier:
    settings: Settings

    async def send_reset_token(self, email: str, token: str) -> None:
        log.info(
            "auth.password_reset_token",
            email=email,
            token=token,
            mode="log",
        )


@dataclass(slots=True)
class SmtpPasswordResetNotifier:
    settings: Settings

    async def send_reset_token(self, email: str, token: str) -> None:
        await asyncio.to_thread(self._send_sync, email, token)

    def _send_sync(self, email: str, token: str) -> None:
        link = f"{self.settings.app_public_base_url}/reset-password?token={token}"
        msg = EmailMessage()
        msg["Subject"] = "Password reset"
        msg["From"] = self.settings.smtp_from
        msg["To"] = email
        msg.set_content(
            "Use this token to reset your password:\n"
            f"{token}\n\n"
            f"Or open link:\n{link}\n"
        )
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=10) as smtp:
            if self.settings.smtp_username and self.settings.smtp_password:
                smtp.starttls()
                smtp.login(self.settings.smtp_username, self.settings.smtp_password)
            smtp.send_message(msg)


def build_password_reset_notifier(settings: Settings) -> PasswordResetNotifier:
    mode = settings.password_reset_delivery_mode.strip().lower()
    if mode == "smtp":
        return SmtpPasswordResetNotifier(settings)
    return LoggingPasswordResetNotifier(settings)


__all__ = [
    "PasswordResetNotifier",
    "LoggingPasswordResetNotifier",
    "SmtpPasswordResetNotifier",
    "build_password_reset_notifier",
]
