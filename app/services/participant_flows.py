"""Participant core flow orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from app.bot.clients import BotClient
from app.bot.menus import MenuAction, build_role_menu
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    build_insight_menu_buttons,
    MISSING_DATA_TEXT,
    NOT_AVAILABLE_TEXT,
    UNKNOWN_USER_TEXT,
    format_goal_view,
    format_planned_steps_view,
    format_progress_view,
)
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import (
    FlowResponse,
    Goal,
    MenuItem,
    PlannedStep,
    TelegramUserContext,
    WeeklyStatus,
)
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
            self.main_bot.send_message(
                chat_id=user.chat_id,
                text=response.text,
                buttons=response.buttons,
            )
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

    def handle_menu_action(
        self,
        user: TelegramUserContext,
        action: MenuAction | str,
        *,
        occurred_at: str,
    ) -> FlowResponse:
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
            self.main_bot.send_message(
                chat_id=user.chat_id,
                text=response.text,
                buttons=response.buttons,
            )
            return response

        normalized_action = _normalize_action(action)
        if normalized_action is MenuAction.VIEW_INSIGHTS:
            return self._send_simple_response(
                user,
                participant=participant,
                text="Мои инсайты",
                flow="insight",
                step="menu",
                occurred_at=occurred_at,
                buttons=build_insight_menu_buttons(),
            )

        if normalized_action in _INERT_ACTIONS:
            return self._send_simple_response(
                user,
                participant=participant,
                text=NOT_AVAILABLE_TEXT,
                flow="idle",
                step=normalized_action.value,
                occurred_at=occurred_at,
            )

        participant_id = _string_value(participant.get("participant_id"))
        if not _optional_string_value(participant.get("team_id")):
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="team_id",
                occurred_at=occurred_at,
            )

        goal_row = self.sheets.get_active_goal(participant_id)
        if goal_row is None:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="active_goal",
                occurred_at=occurred_at,
            )

        goal = _goal_from_row(goal_row)
        if normalized_action is MenuAction.VIEW_GOAL:
            return self._send_simple_response(
                user,
                participant=participant,
                text=format_goal_view(goal),
                flow="view_goal",
                step="render",
                occurred_at=occurred_at,
            )

        steps = [_planned_step_from_row(row) for row in self.sheets.list_planned_steps(participant_id, goal.goal_id)]
        if not steps:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="planned_steps",
                occurred_at=occurred_at,
            )

        if normalized_action is MenuAction.VIEW_STEPS:
            return self._send_simple_response(
                user,
                participant=participant,
                text=format_planned_steps_view(steps),
                flow="view_steps",
                step="render",
                occurred_at=occurred_at,
            )

        if normalized_action is MenuAction.VIEW_PROGRESS:
            weekly_history = [
                _weekly_status_from_row(row)
                for row in self.sheets.list_weekly_status_history(participant_id)
            ]
            return self._send_simple_response(
                user,
                participant=participant,
                text=format_progress_view(steps=steps, weekly_history=weekly_history),
                flow="view_progress",
                step="render",
                occurred_at=occurred_at,
            )

        return self._send_simple_response(
            user,
            participant=participant,
            text=NOT_AVAILABLE_TEXT,
            flow="idle",
            step="unknown_action",
            occurred_at=occurred_at,
        )

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
        self.main_bot.send_message(chat_id=user.chat_id, text=text, menu_items=menu_items)
        return response

    def _send_simple_response(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        text: str,
        flow: str,
        step: str,
        occurred_at: str,
        buttons: tuple[str, ...] = (),
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)
        self.dialog_states.upsert(
            _dialog_state_for(
                user=user,
                participant=participant,
                flow=flow,
                step=step,
                occurred_at=occurred_at,
            )
        )
        self.main_bot.send_message(chat_id=user.chat_id, text=text, buttons=buttons)
        return response

    def _handle_missing_data(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        missing_type: str,
        occurred_at: str,
    ) -> FlowResponse:
        response = self._send_simple_response(
            user,
            participant=participant,
            text=MISSING_DATA_TEXT,
            flow="idle",
            step=f"missing_{missing_type}",
            occurred_at=occurred_at,
        )
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


_INERT_ACTIONS = {
    MenuAction.VIEW_TEAM,
    MenuAction.CAPTAIN_MANUAL_REPORT,
    MenuAction.VIEW_TEAM_REPORT,
}


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


def _normalize_action(action: MenuAction | str) -> MenuAction:
    if isinstance(action, MenuAction):
        return action
    try:
        return MenuAction(action)
    except ValueError:
        return MenuAction.VIEW_INSIGHTS


def _goal_from_row(row: SheetRow) -> Goal:
    return Goal(
        goal_id=_string_value(row.get("goal_id")),
        participant_id=_string_value(row.get("participant_id")),
        goal_title=str(row.get("goal_title") or ""),
        goal_description=str(row.get("goal_description") or ""),
        goal_value_amount=row.get("goal_value_amount"),
        goal_value_currency=_optional_string_value(row.get("goal_value_currency")),
        permission_condition=str(row.get("permission_condition") or ""),
        goal_status=str(row.get("goal_status") or ""),
    )


def _planned_step_from_row(row: SheetRow) -> PlannedStep:
    return PlannedStep(
        step_id=_string_value(row.get("step_id")),
        participant_id=_string_value(row.get("participant_id")),
        goal_id=_string_value(row.get("goal_id")),
        step_number=_int_value(row.get("step_number")),
        step_title=str(row.get("step_title") or ""),
        step_description=str(row.get("step_description") or ""),
        step_status=str(row.get("step_status") or ""),
        closed_week_number=_optional_int_value(row.get("closed_week_number")),
        closed_at=_optional_string_value(row.get("closed_at")),
    )


def _weekly_status_from_row(row: SheetRow) -> WeeklyStatus:
    return WeeklyStatus(
        week_number=_int_value(row.get("week_number")),
        status_symbol=str(row.get("status_symbol") or ""),
        status_code=str(row.get("status_code") or ""),
        submitted_at=_optional_string_value(row.get("submitted_at")),
    )


def _string_value(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("participant_id is required")
    return value


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError("integer value is required")


def _optional_int_value(value: object) -> int | None:
    if value in (None, ""):
        return None
    return _int_value(value)
