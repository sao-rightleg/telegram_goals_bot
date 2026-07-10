"""Telegram bot client boundaries and fake implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

import httpx


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


class TelegramApiError(RuntimeError):
    """Raised when Telegram Bot API returns an error or malformed response."""


@dataclass(frozen=True)
class LiveTelegramBotClient:
    purpose: BotPurpose
    token: str
    http_client: httpx.Client
    api_base_url: str = "https://api.telegram.org"

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        self._post_api(
            "sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
            },
        )
        return OutgoingMessage(chat_id=chat_id, text=text)

    def send_document(
        self,
        *,
        chat_id: str,
        file_path: Path,
        caption: str | None = None,
    ) -> OutgoingDocument:
        if not file_path.is_file():
            raise TelegramApiError(
                f"Telegram sendDocument failed: file not found: {file_path}"
            )

        data = {"chat_id": chat_id}
        if caption is not None:
            data["caption"] = caption
        with file_path.open("rb") as document:
            self._post_api(
                "sendDocument",
                data=data,
                files={"document": (file_path.name, document)},
            )
        return OutgoingDocument(chat_id=chat_id, file_path=file_path, caption=caption)

    def get_updates(
        self,
        *,
        offset: int | None,
        timeout_seconds: int,
        limit: int,
    ) -> list[dict[str, object]]:
        data = {
            "timeout": str(timeout_seconds),
            "limit": str(limit),
        }
        if offset is not None:
            data["offset"] = str(offset)
        payload = self._post_api("getUpdates", data=data)
        result = payload.get("result")
        if not isinstance(result, list):
            raise TelegramApiError("Telegram getUpdates failed: malformed result")
        return [item for item in result if isinstance(item, dict)]

    def _post_api(
        self,
        method: str,
        *,
        data: dict[str, str],
        files: dict[str, object] | None = None,
    ) -> dict[str, object]:
        try:
            response = self.http_client.post(
                _api_url(self.api_base_url, self.token, method),
                data=data,
                files=files,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramApiError(
                f"Telegram {method} request failed: {_sanitize_token(str(exc), self.token)}"
            ) from exc
        return _parse_telegram_json(response, method=method, token=self.token)


@dataclass(frozen=True)
class LiveTelegramFileDownloader:
    token: str
    http_client: httpx.Client
    api_base_url: str = "https://api.telegram.org"

    def download_file(self, request: TelegramFileDownload) -> Path:
        metadata = self._post_api(
            "getFile",
            data={"file_id": request.telegram_file_id},
        )
        result = metadata.get("result")
        if not isinstance(result, dict) or not isinstance(result.get("file_path"), str):
            raise TelegramApiError("Telegram getFile failed: missing file_path")

        file_path = result["file_path"]
        try:
            response = self.http_client.get(
                _file_url(self.api_base_url, self.token, file_path)
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramApiError(
                f"Telegram file download failed: {_sanitize_token(str(exc), self.token)}"
            ) from exc

        request.destination_path.parent.mkdir(parents=True, exist_ok=True)
        request.destination_path.write_bytes(response.content)
        return request.destination_path

    def _post_api(self, method: str, *, data: dict[str, str]) -> dict[str, object]:
        try:
            response = self.http_client.post(
                _api_url(self.api_base_url, self.token, method),
                data=data,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramApiError(
                f"Telegram {method} request failed: {_sanitize_token(str(exc), self.token)}"
            ) from exc
        return _parse_telegram_json(response, method=method, token=self.token)


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


def _api_url(base_url: str, token: str, method: str) -> str:
    return f"{base_url.rstrip('/')}/bot{token}/{method}"


def _file_url(base_url: str, token: str, file_path: str) -> str:
    return f"{base_url.rstrip('/')}/file/bot{token}/{file_path.lstrip('/')}"


def _parse_telegram_json(
    response: httpx.Response,
    *,
    method: str,
    token: str,
) -> dict[str, object]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TelegramApiError(f"Telegram {method} failed: invalid JSON response") from exc

    if not isinstance(payload, dict):
        raise TelegramApiError(f"Telegram {method} failed: invalid JSON response")
    if payload.get("ok") is not True:
        description = payload.get("description")
        if not isinstance(description, str):
            description = "unknown Telegram API error"
        raise TelegramApiError(
            f"Telegram {method} failed: {_sanitize_token(description, token)}"
        )
    return payload


def _sanitize_token(text: str, token: str) -> str:
    return text.replace(token, "[REDACTED]")
