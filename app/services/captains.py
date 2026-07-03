"""Captain-only service flows."""

from __future__ import annotations

from dataclasses import dataclass

from app.bot.clients import BotClient
from app.bot.messages import (
    CAPTAIN_NO_TEAM_MEMBERS_TEXT,
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_TEAM_TITLE_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
    format_captain_team_member_line,
)
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.sheets.gateway import SheetRow, SheetsGateway


@dataclass(frozen=True)
class CaptainService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter

    def show_team(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        captain = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if captain is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)

        if not _consent_is_given(captain):
            response = FlowResponse(
                chat_id=user.chat_id,
                text=CONSENT_TEXT,
                buttons=(CONSENT_ACCEPT_BUTTON,),
            )
            self.main_bot.send_message(chat_id=user.chat_id, text=response.text)
            return response

        if _role(captain) != "captain":
            return self._send_response(user, text=CAPTAIN_ONLY_TEXT)

        team_id = _optional_string_value(captain.get("team_id"))
        if team_id is None:
            return self._handle_missing_data(
                user,
                participant=captain,
                missing_type="team_id",
                occurred_at=occurred_at,
            )

        team_members = self.sheets.list_participants_by_team(team_id)
        return self._send_response(user, text=_format_team_view(team_members))

    def _send_response(self, user: TelegramUserContext, *, text: str) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text)
        self.main_bot.send_message(chat_id=user.chat_id, text=text)
        return response

    def _handle_missing_data(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        missing_type: str,
        occurred_at: str,
    ) -> FlowResponse:
        response = self._send_response(user, text=MISSING_DATA_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_missing_data_error_text(user, participant, missing_type, occurred_at),
            recipients=(),
        )
        return response

    def _handle_unknown_user(
        self,
        user: TelegramUserContext,
        *,
        occurred_at: str,
    ) -> FlowResponse:
        response = self._send_response(user, text=UNKNOWN_USER_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_unknown_user_error_text(user, occurred_at),
            recipients=(),
        )
        return response


def _format_team_view(team_members: list[SheetRow]) -> str:
    if not team_members:
        return CAPTAIN_NO_TEAM_MEMBERS_TEXT

    sorted_members = sorted(team_members, key=_team_member_sort_key)
    return "\n".join(
        [CAPTAIN_TEAM_TITLE_TEXT]
        + [format_captain_team_member_line(member) for member in sorted_members]
    )


def _team_member_sort_key(participant: SheetRow) -> tuple[str, str]:
    display_name = (
        _optional_string_value(participant.get("full_name"))
        or _optional_string_value(participant.get("display_name"))
        or _optional_string_value(participant.get("name"))
        or ""
    )
    participant_id = _optional_string_value(participant.get("participant_id")) or ""
    return (display_name.lower(), participant_id)


def _consent_is_given(participant: SheetRow) -> bool:
    value = participant.get("consent_given")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "да"}
    return False


def _role(participant: SheetRow) -> str:
    value = participant.get("role")
    return value if isinstance(value, str) else "participant"


def _unknown_user_error_text(user: TelegramUserContext, occurred_at: str) -> str:
    username = user.username if user.username else "unknown"
    return (
        "unknown_telegram_user "
        f"telegram_id={user.telegram_id} "
        f"username={username} "
        f"occurred_at={occurred_at}"
    )


def _missing_data_error_text(
    user: TelegramUserContext,
    participant: SheetRow,
    missing_type: str,
    occurred_at: str,
) -> str:
    participant_id = _optional_string_value(participant.get("participant_id")) or "unknown"
    return (
        "missing_required_data "
        f"type={missing_type} "
        f"telegram_id={user.telegram_id} "
        f"participant_id={participant_id} "
        f"occurred_at={occurred_at}"
    )


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
