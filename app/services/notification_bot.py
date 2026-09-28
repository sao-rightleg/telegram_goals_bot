"""Captain connection flow for the outbound notification bot."""

from __future__ import annotations

from dataclasses import dataclass

from app.bot.clients import BotClient
from app.services.participant_models import FlowResponse
from app.services.team_captains import list_team_captain_assignments
from app.sheets.gateway import SheetsGateway


NOTIFICATION_BOT_CONNECTED_TEXT = (
    "Бот уведомлений подключён. Сюда будут приходить сводки и отчёты вашей команды."
)
NOTIFICATION_BOT_FORBIDDEN_TEXT = (
    "Не удалось подключить бот уведомлений. Обратитесь к администратору."
)


@dataclass(frozen=True)
class NotificationBotStartService:
    sheets: SheetsGateway
    notification_bot: BotClient
    flow_id: str

    def handle_start(
        self,
        *,
        telegram_id: int,
        chat_id: str,
        occurred_at: str,
    ) -> FlowResponse:
        assignments = self._eligible_assignments(telegram_id=telegram_id, chat_id=chat_id)
        if not assignments:
            return self._reply(chat_id=chat_id, text=NOTIFICATION_BOT_FORBIDDEN_TEXT)

        for row in assignments:
            self.sheets.mark_team_captain_notification_started(
                flow_id=self.flow_id,
                captain_id=str(row["captain_id"]),
                team_id=str(row["team_id"]),
                captain_telegram_id=telegram_id,
                chat_id=chat_id,
                started_at=occurred_at,
                create_if_missing=row.get("_assignment_source") == "legacy_teams",
                captain_full_name=self._captain_full_name(str(row["captain_id"])),
            )
        return self._reply(chat_id=chat_id, text=NOTIFICATION_BOT_CONNECTED_TEXT)

    def _eligible_assignments(self, *, telegram_id: int, chat_id: str) -> list[dict[str, object]]:
        if chat_id != str(telegram_id):
            return []
        return [
            row for row in list_team_captain_assignments(
                self.sheets,
                default_flow_id=self.flow_id,
            )
            if str(row.get("flow_id", "")).strip() == self.flow_id
            and _integer_value(row.get("captain_telegram_id")) == telegram_id
            and str(row.get("captain_id", "")).strip()
            and str(row.get("team_id", "")).strip()
            and _is_true(row.get("is_active"))
        ]

    def _captain_full_name(self, captain_id: str) -> str:
        participant = self.sheets.get_participant(captain_id)
        return str((participant or {}).get("full_name") or "").strip()

    def _reply(self, *, chat_id: str, text: str) -> FlowResponse:
        self.notification_bot.send_message(chat_id=chat_id, text=text)
        return FlowResponse(chat_id=chat_id, text=text)

def _integer_value(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _is_true(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"
