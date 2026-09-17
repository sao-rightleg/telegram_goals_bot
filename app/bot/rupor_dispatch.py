"""Thin Telegram update dispatcher for the RUPOR control bot."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Callable, Mapping
from zoneinfo import ZoneInfo

from app.bot.dispatch import parse_telegram_update
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.participant_models import FlowResponse
from app.services.rupor import RuporService


def _now() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE_NAME))


@dataclass(frozen=True)
class RuporUpdateDispatcher:
    service: RuporService
    now_provider: Callable[[], datetime] = _now

    def resume_incomplete(self) -> int:
        return self.service.resume_incomplete(occurred_at=self.now_provider().isoformat())

    def dispatch_update(self, payload: Mapping[str, object]) -> FlowResponse | None:
        update = parse_telegram_update(payload)
        occurred_at = self.now_provider().isoformat()
        if update.message is not None:
            message = update.message
            if message.command == "/start":
                return self.service.handle_start(
                    telegram_id=message.telegram_id,
                    chat_id=message.chat_id,
                    occurred_at=occurred_at,
                )
            if message.text is not None:
                return self.service.receive_text(
                    telegram_id=message.telegram_id,
                    chat_id=message.chat_id,
                    text=message.text,
                    occurred_at=occurred_at,
                )
            return None
        if update.callback is not None:
            callback = update.callback
            return self.service.handle_callback(
                telegram_id=callback.telegram_id,
                chat_id=callback.chat_id,
                callback_data=callback.data,
                occurred_at=occurred_at,
            )
        return None
