"""Thin update dispatcher for the notification bot connection flow."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.bot.dispatch import parse_telegram_update
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notification_bot import NotificationBotStartService
from app.services.participant_models import FlowResponse


def _now() -> datetime:
    return datetime.now(ZoneInfo(TIMEZONE_NAME))


@dataclass(frozen=True)
class NotificationBotUpdateDispatcher:
    service: NotificationBotStartService
    now_provider: Callable[[], datetime] = _now

    def dispatch_update(self, payload: Mapping[str, object]) -> FlowResponse | None:
        update = parse_telegram_update(payload)
        message = update.message
        if message is None or message.command != "/start":
            return None
        return self.service.handle_start(
            telegram_id=message.telegram_id,
            chat_id=message.chat_id,
            occurred_at=self.now_provider().isoformat(),
        )
