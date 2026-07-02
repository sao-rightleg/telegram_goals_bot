"""Participant core flow orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from app.bot.clients import BotClient
from app.bot.menus import build_role_menu
from app.bot.messages import CONSENT_ACCEPT_BUTTON, CONSENT_TEXT, UNKNOWN_USER_TEXT
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, MenuItem, TelegramUserContext
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.dialog_state import DialogState, DialogStateRepository


@dataclass(frozen=True)
class ParticipantFlowService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    dialog_states: DialogStateRepository

    def handle_start(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)

        if not _consent_is_given(participant):
            response = FlowResponse(
                chat_id=user.chat_id,
                text=CONSENT_TEXT,
                buttons=(CONSENT_ACCEPT_BUTTON,),
            )
            self.dialog_states.upsert(
                _dialog_state_for(
                    user=user,
                    participant=participant,
                    flow="consent",
                    step="awaiting_consent",
                    occurred_at=occurred_at,
                )
            )
            self.main_bot.send_message(chat_id=user.chat_id, text=response.text)
            return response

        return self._show_menu(user, participant=participant, occurred_at=occurred_at)

    def accept_consent(self, user: TelegramUserContext, *, consent_given_at: str) -> FlowResponse:
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=consent_given_at)

        participant_id = _string_value(participant.get("participant_id"))
        self.sheets.update_participant_consent(
            participant_id,
            consent_given=True,
            consent_given_at=consent_given_at,
        )
        participant = dict(participant)
        participant["consent_given"] = True
        participant["consent_given_at"] = consent_given_at
        return self._show_menu(user, participant=participant, occurred_at=consent_given_at)

    def _show_menu(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        occurred_at: str,
    ) -> FlowResponse:
        menu_items = build_role_menu(_role(participant))
        text = _menu_text(menu_items)
        response = FlowResponse(chat_id=user.chat_id, text=text, menu_items=menu_items)
        self.dialog_states.upsert(
            _dialog_state_for(
                user=user,
                participant=participant,
                flow="idle",
                step="menu",
                occurred_at=occurred_at,
            )
        )
        self.main_bot.send_message(chat_id=user.chat_id, text=text)
        return response

    def _handle_unknown_user(
        self,
        user: TelegramUserContext,
        *,
        occurred_at: str,
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=UNKNOWN_USER_TEXT)
        self.main_bot.send_message(chat_id=user.chat_id, text=response.text)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_unknown_user_error_text(user, occurred_at),
            recipients=(),
        )
        return response


def _dialog_state_for(
    *,
    user: TelegramUserContext,
    participant: SheetRow,
    flow: str,
    step: str,
    occurred_at: str,
) -> DialogState:
    return DialogState(
        telegram_id=user.telegram_id,
        participant_id=_optional_string_value(participant.get("participant_id")),
        role=_optional_string_value(participant.get("role")),
        flow=flow,
        step=step,
        started_at=occurred_at,
        updated_at=occurred_at,
    )


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


def _menu_text(menu_items: tuple[MenuItem, ...]) -> str:
    return "\n".join(item.label for item in menu_items)


def _unknown_user_error_text(user: TelegramUserContext, occurred_at: str) -> str:
    username = user.username if user.username else "unknown"
    return (
        "unknown_telegram_user "
        f"telegram_id={user.telegram_id} "
        f"username={username} "
        f"occurred_at={occurred_at}"
    )


def _string_value(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("participant_id is required")
    return value


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
