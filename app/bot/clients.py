"""Telegram bot client boundaries and fake implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class BotPurpose(str, Enum):
    MAIN = "main"
    ERROR = "error"
    NOTIFICATION = "notification"


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str


class BotClient(Protocol):
    purpose: BotPurpose

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        """Send a text message through a concrete bot client."""


@dataclass
class FakeBotClient:
    purpose: BotPurpose
    sent_messages: list[OutgoingMessage] = field(default_factory=list)

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        message = OutgoingMessage(chat_id=chat_id, text=text)
        self.sent_messages.append(message)
        return message
