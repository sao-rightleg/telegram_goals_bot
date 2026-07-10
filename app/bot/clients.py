"""Telegram bot client boundaries and fake implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

import httpx

from app.bot.menus import (
    CONSENT_ACCEPT_CALLBACK,
    INSIGHT_ADD_CALLBACK,
    INSIGHT_CANCEL_CALLBACK,
    INSIGHT_DONE_CALLBACK,
    INSIGHT_LIST_CALLBACK_PREFIX,
    MENU_CALLBACK_PREFIX,
    WEEKLY_REPORT_DONE_CALLBACK,
    WEEKLY_REPORT_STATUS_CALLBACK_PREFIX,
)
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    INSIGHT_ADD_BUTTON,
    INSIGHT_CANCEL_BUTTON,
    INSIGHT_DONE_BUTTON,
    INSIGHT_LIST_BUTTON,
    WEEKLY_REPORT_BLUE_BUTTON,
    WEEKLY_REPORT_DONE_BUTTON,
    WEEKLY_REPORT_GREEN_BUTTON,
    WEEKLY_REPORT_RED_BUTTON,
)
from app.services.participant_models import MenuItem


class BotPurpose(str, Enum):
    MAIN = "main"
    ERROR = "error"
    NOTIFICATION = "notification"


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
    buttons: tuple["TelegramInlineButton", ...] = ()
    menu_items: tuple[MenuItem, ...] = ()


@dataclass(frozen=True)
class TelegramInlineButton:
    text: str
    callback_data: str


@dataclass(frozen=True)
class OutgoingDocument:
    chat_id: str
    file_path: Path
    caption: str | None = None


class BotClient(Protocol):
    purpose: BotPurpose

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        buttons: tuple[str | TelegramInlineButton, ...] = (),
        menu_items: tuple[MenuItem, ...] = (),
    ) -> OutgoingMessage:
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

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        buttons: tuple[str | TelegramInlineButton, ...] = (),
        menu_items: tuple[MenuItem, ...] = (),
    ) -> OutgoingMessage:
        inline_buttons = _normalize_inline_buttons(buttons=buttons, menu_items=menu_items)
        data = {
            "chat_id": chat_id,
            "text": text,
        }
        if inline_buttons:
            data["reply_markup"] = _inline_keyboard_markup(inline_buttons)
        self._post_api(
            "sendMessage",
            data=data,
        )
        return OutgoingMessage(
            chat_id=chat_id,
            text=text,
            buttons=inline_buttons,
            menu_items=menu_items,
        )

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

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        buttons: tuple[str | TelegramInlineButton, ...] = (),
        menu_items: tuple[MenuItem, ...] = (),
    ) -> OutgoingMessage:
        message = OutgoingMessage(
            chat_id=chat_id,
            text=text,
            buttons=_normalize_inline_buttons(buttons=buttons, menu_items=menu_items),
            menu_items=menu_items,
        )
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


def _normalize_inline_buttons(
    *,
    buttons: tuple[str | TelegramInlineButton, ...] = (),
    menu_items: tuple[MenuItem, ...] = (),
) -> tuple[TelegramInlineButton, ...]:
    normalized = []
    for button in buttons:
        if isinstance(button, TelegramInlineButton):
            normalized.append(button)
            continue
        callback_data = _callback_data_for_button(button)
        if callback_data is not None:
            normalized.append(TelegramInlineButton(text=button, callback_data=callback_data))

    normalized.extend(
        TelegramInlineButton(
            text=item.label,
            callback_data=f"{MENU_CALLBACK_PREFIX}{_menu_action_value(item)}",
        )
        for item in menu_items
    )
    return tuple(normalized)


def _menu_action_value(item: MenuItem) -> str:
    action = item.action
    value = getattr(action, "value", action)
    return str(value)


def _callback_data_for_button(text: str) -> str | None:
    return _BUTTON_CALLBACKS.get(text)


def _inline_keyboard_markup(buttons: tuple[TelegramInlineButton, ...]) -> str:
    return json.dumps(
        {
            "inline_keyboard": [
                [{"text": button.text, "callback_data": button.callback_data}]
                for button in buttons
            ]
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


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


_BUTTON_CALLBACKS = {
    CONSENT_ACCEPT_BUTTON: CONSENT_ACCEPT_CALLBACK,
    WEEKLY_REPORT_GREEN_BUTTON: f"{WEEKLY_REPORT_STATUS_CALLBACK_PREFIX}green",
    WEEKLY_REPORT_BLUE_BUTTON: f"{WEEKLY_REPORT_STATUS_CALLBACK_PREFIX}blue",
    WEEKLY_REPORT_RED_BUTTON: f"{WEEKLY_REPORT_STATUS_CALLBACK_PREFIX}red",
    WEEKLY_REPORT_DONE_BUTTON: WEEKLY_REPORT_DONE_CALLBACK,
    INSIGHT_ADD_BUTTON: INSIGHT_ADD_CALLBACK,
    INSIGHT_LIST_BUTTON: f"{INSIGHT_LIST_CALLBACK_PREFIX}0",
    INSIGHT_DONE_BUTTON: INSIGHT_DONE_CALLBACK,
    INSIGHT_CANCEL_BUTTON: INSIGHT_CANCEL_CALLBACK,
}
