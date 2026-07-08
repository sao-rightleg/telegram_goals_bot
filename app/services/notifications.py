"""Notification routing boundary for the three-bot MVP model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from app.bot.clients import BotClient, OutgoingDocument, OutgoingMessage


class NotificationCategory(str, Enum):
    PARTICIPANT_MESSAGE = "participant_message"
    TECHNICAL_ERROR = "technical_error"
    OPERATIONAL_NOTIFICATION = "operational_notification"
    REPORT_DELIVERY = "report_delivery"


class RecipientType(str, Enum):
    PARTICIPANT = "participant"
    CAPTAIN = "captain"
    TRACKER = "tracker"
    ADMIN = "admin"
    ADMIN_ERROR_CHAT = "admin_error_chat"
    SITNIKOV = "sitnikov"


@dataclass(frozen=True)
class Recipient:
    recipient_type: RecipientType
    chat_id: str


@dataclass(frozen=True)
class NotificationRouter:
    main_bot: BotClient
    error_bot: BotClient
    notification_bot: BotClient
    admin_error_recipient: Recipient

    def send(
        self,
        *,
        category: NotificationCategory,
        text: str,
        recipients: Iterable[Recipient],
    ) -> list[OutgoingMessage]:
        if category is NotificationCategory.TECHNICAL_ERROR:
            return [
                self.error_bot.send_message(
                    chat_id=self.admin_error_recipient.chat_id,
                    text=text,
                )
            ]

        bot = (
            self.main_bot
            if category is NotificationCategory.PARTICIPANT_MESSAGE
            else self.notification_bot
        )
        return [bot.send_message(chat_id=recipient.chat_id, text=text) for recipient in recipients]

    def send_document(
        self,
        *,
        category: NotificationCategory,
        file_path: Path,
        recipients: Iterable[Recipient],
        caption: str | None = None,
    ) -> list[OutgoingDocument]:
        bot = (
            self.main_bot
            if category is NotificationCategory.PARTICIPANT_MESSAGE
            else self.notification_bot
        )
        return [
            bot.send_document(
                chat_id=recipient.chat_id,
                file_path=file_path,
                caption=caption,
            )
            for recipient in recipients
        ]
