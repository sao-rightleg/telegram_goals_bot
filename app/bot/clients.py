"""Telegram bot client boundaries and fake implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol


class BotPurpose(str, Enum):
    MAIN = "main"
    ERROR = "error"
    NOTIFICATION = "notification"


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str


@dataclass(frozen=True)
class OutgoingDocument:
    chat_id: str
    file_path: Path
    caption: str | None = None


class BotClient(Protocol):
    purpose: BotPurpose

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        """Send a text message through a concrete bot client."""

    def send_document(
        self,
        *,
        chat_id: str,
        file_path: Path,
        caption: str | None = None,
    ) -> OutgoingDocument:
        """Send a document through a concrete bot client."""


@dataclass(frozen=True)
class TelegramFileDownload:
    telegram_file_id: str
    destination_path: Path


class TelegramFileDownloader(Protocol):
    def download_file(self, request: TelegramFileDownload) -> Path:
        """Download a Telegram file into the requested local destination."""


@dataclass
class FakeBotClient:
    purpose: BotPurpose
    sent_messages: list[OutgoingMessage] = field(default_factory=list)
    sent_documents: list[OutgoingDocument] = field(default_factory=list)

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        message = OutgoingMessage(chat_id=chat_id, text=text)
        self.sent_messages.append(message)
        return message

    def send_document(
        self,
        *,
        chat_id: str,
        file_path: Path,
        caption: str | None = None,
    ) -> OutgoingDocument:
        document = OutgoingDocument(chat_id=chat_id, file_path=file_path, caption=caption)
        self.sent_documents.append(document)
        return document


@dataclass
class FakeTelegramFileDownloader:
    downloads: list[TelegramFileDownload] = field(default_factory=list)

    def download_file(self, request: TelegramFileDownload) -> Path:
        request.destination_path.parent.mkdir(parents=True, exist_ok=True)
        request.destination_path.write_bytes(
            f"fake telegram voice file: {request.telegram_file_id}".encode("utf-8")
        )
        self.downloads.append(request)
        return request.destination_path
