"""Participant core flow orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from app.bot.clients import BotClient, TelegramInlineButton
from app.bot.menus import (
    MenuAction,
    WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX,
    WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX,
    WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX,
    build_role_menu,
)
from app.bot.messages import (
    CHALLENGE_STAGES_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_ACCEPTED_INTRO_TEXT,
    CONSENT_DECLINE_BUTTON,
    CONSENT_DECLINE_CONFIRM_BUTTON,
    CONSENT_DECLINE_CONFIRM_TEXT,
    CONSENT_DECLINE_RECONSIDER_BUTTON,
    CONSENT_DECLINED_TEXT,
    CONSENT_TEXT,
    GOAL_SETUP_INTRO_TEXT,
    TELEGRAM_HTML_PARSE_MODE,
    WEEKLY_REPORT_EDIT_STEP_BUTTON,
    WEEKLY_REPORT_START_STEP_BUTTON,
    build_insight_menu_buttons,
    MISSING_DATA_TEXT,
    NOT_AVAILABLE_TEXT,
    UNKNOWN_USER_TEXT,
    format_goal_view,
    format_planned_steps_view,
    format_progress_view,
)
from app.scheduler.calendar import (
    challenge_week_date_range,
    closed_challenge_week_count,
    current_challenge_week_number,
    is_working_week,
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
from app.storage.registration import RegistrationDraft, RegistrationDraftRepository


class RegistrationClosedError(RuntimeError):
    """Raised when an unfinished registration no longer belongs to an open window."""


@dataclass(frozen=True)
class ParticipantFlowService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    dialog_states: DialogStateRepository
    registration_flows: SheetsGateway | None = None
    registration_drafts: RegistrationDraftRepository | None = None

    def handle_start(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is None:
            return self._handle_registration_start(user, occurred_at=occurred_at)

        participant_id = _string_value(participant.get("participant_id"))
        self.sheets.mark_participant_bot_started(participant_id, started_at=occurred_at)
        participant = dict(participant)
        participant.setdefault("bot_started_at", occurred_at)
        participant["participant_stage"] = "onboarding"

        if not _consent_is_given(participant):
            response = FlowResponse(
                chat_id=user.chat_id,
                text=CONSENT_TEXT,
                buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON),
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
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is None:
            return self._accept_registration_consent(user, occurred_at=consent_given_at)

        participant_id = _string_value(participant.get("participant_id"))
        self.sheets.update_participant_consent(
            participant_id,
            consent_given=True,
            consent_given_at=consent_given_at,
        )
        participant = dict(participant)
        participant["consent_given"] = True
        participant["consent_given_at"] = consent_given_at
        participant["participant_stage"] = "goal_setup"
        intro_response = self._send_simple_response(
            user,
            participant=participant,
            text=_onboarding_intro_text(),
            flow="idle",
            step="onboarding_completed",
            occurred_at=consent_given_at,
        )
        self._show_menu(user, participant=participant, occurred_at=consent_given_at)
        return intro_response

    def handle_registration_text(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        occurred_at: str,
    ) -> FlowResponse:
        draft = self._valid_registration_draft(user, occurred_at=occurred_at)
        state = self.dialog_states.get(user.telegram_id)
        value = " ".join(text.strip().split())
        if not value or len(value) > 80:
            return self._send_registration_response(user, "Напиши значение длиной до 80 символов.")
        if state is None or state.flow != "registration":
            return self._handle_registration_start(user, occurred_at=occurred_at)
        if state.step == "awaiting_first_name":
            self._registration_repository().update(user.telegram_id, first_name=value, updated_at=occurred_at)
            self._set_registration_state(user, step="awaiting_last_name", draft=draft, occurred_at=occurred_at)
            return self._send_registration_response(user, "Напиши фамилию.")
        if state.step == "awaiting_last_name":
            draft = self._registration_repository().update(
                user.telegram_id,
                last_name=value,
                updated_at=occurred_at,
            )
            return self._show_registration_captains(user, draft=draft, occurred_at=occurred_at)
        return self._send_registration_response(user, "Продолжи регистрацию кнопками в предыдущем сообщении.")

    def select_registration_captain(
        self,
        user: TelegramUserContext,
        *,
        captain_id: str,
        occurred_at: str,
    ) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is not None:
            return self._show_menu(user, participant=participant, occurred_at=occurred_at)
        draft = self._valid_registration_draft(user, occurred_at=occurred_at)
        state = self.dialog_states.get(user.telegram_id)
        if state is None or state.flow != "registration" or state.step != "awaiting_captain":
            return self._resume_registration(user, draft=draft, occurred_at=occurred_at)
        captain = self._captain_for_flow(draft.flow_id, captain_id)
        if captain is None:
            return self._show_registration_captains(user, draft=draft, occurred_at=occurred_at)
        draft = self._registration_repository().update(
            user.telegram_id,
            captain_id=captain_id,
            updated_at=occurred_at,
        )
        self._set_registration_state(user, step="awaiting_confirmation", draft=draft, occurred_at=occurred_at)
        text = (
            "Проверь данные:\n\n"
            f"Имя и фамилия: {draft.first_name} {draft.last_name}\n"
            f"Капитан: {_participant_name(captain)}"
        )
        buttons = (
            TelegramInlineButton("✅ Подтвердить", "registration:confirm"),
            TelegramInlineButton("Изменить имя", "registration:edit_first_name"),
            TelegramInlineButton("Изменить фамилию", "registration:edit_last_name"),
        )
        return self._send_registration_response(user, text, buttons=buttons)

    def edit_registration_name(self, user: TelegramUserContext, *, field: str, occurred_at: str) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is not None:
            return self._show_menu(user, participant=participant, occurred_at=occurred_at)
        draft = self._valid_registration_draft(user, occurred_at=occurred_at)
        state = self.dialog_states.get(user.telegram_id)
        if state is None or state.flow != "registration" or state.step != "awaiting_confirmation":
            return self._resume_registration(user, draft=draft, occurred_at=occurred_at)
        step = "awaiting_first_name" if field == "first_name" else "awaiting_last_name"
        draft = self._registration_repository().update(
            user.telegram_id,
            updated_at=occurred_at,
            **{field: None, "captain_id": None},
        )
        self._set_registration_state(user, step=step, draft=draft, occurred_at=occurred_at)
        prompt = "Как тебя зовут? Напиши только имя." if field == "first_name" else "Напиши фамилию."
        return self._send_registration_response(user, prompt)

    def confirm_registration(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is not None:
            return self._show_menu(user, participant=participant, occurred_at=occurred_at)
        draft = self._valid_registration_draft(user, occurred_at=occurred_at)
        state = self.dialog_states.get(user.telegram_id)
        if state is None or state.flow != "registration" or state.step != "awaiting_confirmation":
            return self._resume_registration(user, draft=draft, occurred_at=occurred_at)
        if not all((draft.consent_given_at, draft.first_name, draft.last_name, draft.captain_id)):
            return self._handle_registration_start(user, occurred_at=occurred_at)
        captain = self._captain_for_flow(draft.flow_id, draft.captain_id)
        if captain is None:
            return self._show_registration_captains(user, draft=draft, occurred_at=occurred_at)
        claim_token = uuid4().hex
        stale_before = (datetime.fromisoformat(occurred_at) - timedelta(minutes=10)).isoformat()
        if not self._registration_repository().claim_finalization(
            user.telegram_id,
            claim_token=claim_token,
            updated_at=occurred_at,
            stale_before=stale_before,
        ):
            participant = self._participant_for_current_flow(user.telegram_id)
            if participant is not None:
                return self._show_menu(user, participant=participant, occurred_at=occurred_at)
            return self._send_registration_response(user, "Регистрация уже обрабатывается. Повтори /start через минуту.")
        existing = self.sheets.find_participant_in_flow(draft.flow_id, user.telegram_id)
        if existing is None:
            team_id = _string_value(captain.get("team_id"))
            team = next(
                (row for row in self.sheets.list_teams() if row.get("flow_id") == draft.flow_id and row.get("team_id") == team_id),
                {},
            )
            participant_id = _registration_participant_id(draft.flow_id, user.telegram_id)
            try:
                self.sheets.append_participant(
                    {
                    "flow_id": draft.flow_id,
                    "participant_id": participant_id,
                    "telegram_id": user.telegram_id,
                    "username": user.username or "",
                    "first_name": draft.first_name,
                    "last_name": draft.last_name,
                    "full_name": f"{draft.first_name} {draft.last_name}",
                    "role": "participant",
                    "team_id": team_id,
                    "team_name": team.get("team_name", captain.get("team_name", "")),
                    "captain_id": draft.captain_id,
                    "tracker_id": team.get("tracker_id", ""),
                    "status": "active",
                    "participant_stage": "goal_setup",
                    "consent_given": True,
                    "consent_given_at": draft.consent_given_at,
                    "consent_status": "accepted",
                    "bot_started_at": draft.created_at,
                    "onboarding_completed_at": occurred_at,
                    "last_stage_updated_at": occurred_at,
                    "created_at": occurred_at,
                    "updated_at": occurred_at,
                    }
                )
            except Exception:
                self._registration_repository().release_finalization(
                    user.telegram_id,
                    claim_token=claim_token,
                    updated_at=occurred_at,
                )
                raise
        participant = self.sheets.find_participant_in_flow(draft.flow_id, user.telegram_id)
        if participant is None:
            raise RuntimeError("Participant registration write was not visible")
        captain = self._captain_for_flow(draft.flow_id, draft.captain_id)
        flow = self._active_registration_flow()
        text = _registration_success_text(participant, captain or {}, flow or {})
        self._registration_repository().clear(user.telegram_id)
        self.dialog_states.upsert(
            _dialog_state_for(user=user, participant=participant, flow="idle", step="menu", occurred_at=occurred_at)
        )
        return self._send_registration_response(user, text)

    def decline_consent(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is None:
            draft = self.registration_drafts.get(user.telegram_id) if self.registration_drafts else None
            if draft is None:
                flow = self._active_registration_flow()
                if flow is None:
                    return self._handle_unknown_user(user, occurred_at=occurred_at)
                opens_at, closes_at = _registration_window(flow)
                now = datetime.fromisoformat(occurred_at)
                if now < opens_at or now > closes_at:
                    return self._send_registration_response(user, "Данный поток уже набран")
                return self._send_registration_response(
                    user,
                    CONSENT_DECLINE_CONFIRM_TEXT,
                    buttons=(CONSENT_DECLINE_RECONSIDER_BUTTON, CONSENT_DECLINE_CONFIRM_BUTTON),
                )
            self._set_registration_state(
                user,
                step="awaiting_consent_decline_confirmation",
                draft=draft,
                occurred_at=occurred_at,
            )
            return self._send_registration_response(
                user,
                CONSENT_DECLINE_CONFIRM_TEXT,
                buttons=(CONSENT_DECLINE_RECONSIDER_BUTTON, CONSENT_DECLINE_CONFIRM_BUTTON),
            )
        return self._send_simple_response(
            user,
            participant=participant,
            text=CONSENT_DECLINE_CONFIRM_TEXT,
            flow="consent",
            step="awaiting_consent_decline_confirmation",
            occurred_at=occurred_at,
            buttons=(CONSENT_DECLINE_RECONSIDER_BUTTON, CONSENT_DECLINE_CONFIRM_BUTTON),
        )

    def confirm_consent_decline(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        participant = self._participant_for_current_flow(user.telegram_id)
        if participant is None:
            draft = self.registration_drafts.get(user.telegram_id) if self.registration_drafts else None
            if draft is None:
                return self._send_registration_response(user, CONSENT_DECLINED_TEXT)
            self.registration_drafts.clear(user.telegram_id)
            self.dialog_states.clear(user.telegram_id)
            return self._send_registration_response(user, CONSENT_DECLINED_TEXT)

        participant_id = _string_value(participant.get("participant_id"))
        self.sheets.update_participant_consent(
            participant_id,
            consent_given=False,
            consent_given_at=occurred_at,
        )
        return self._send_simple_response(
            user,
            participant=participant,
            text=CONSENT_DECLINED_TEXT,
            flow="consent",
            step="declined",
            occurred_at=occurred_at,
        )

    def select_weekly_focus(
        self,
        user: TelegramUserContext,
        *,
        step_id: str,
        occurred_at: str,
    ) -> FlowResponse:
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)
        if not _consent_is_given(participant):
            return self._send_consent_response(user, participant=participant, occurred_at=occurred_at)

        participant_id = _string_value(participant.get("participant_id"))
        goal_row = self.sheets.get_active_goal(participant_id)
        if goal_row is None:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="active_goal",
                occurred_at=occurred_at,
            )

        goal = _goal_from_row(goal_row)
        week_number = current_challenge_week_number(datetime.fromisoformat(occurred_at))
        existing = self.sheets.find_weekly_focus(participant_id, week_number=week_number)
        if existing is not None:
            return self._send_simple_response(
                user,
                participant=participant,
                text="Фокус этой недели уже выбран. Внутри недели его нельзя менять.",
                flow="idle",
                step="weekly_focus_locked",
                occurred_at=occurred_at,
            )

        steps = [_planned_step_from_row(row) for row in self.sheets.list_planned_steps(participant_id, goal.goal_id)]
        selected_step = _step_by_id([step for step in steps if step.step_status != "closed"], step_id)
        start_date, end_date = challenge_week_date_range(datetime.fromisoformat(occurred_at))
        self.sheets.append_weekly_focus(
            {
                "focus_id": _weekly_focus_id(participant_id, week_number),
                "participant_id": participant_id,
                "goal_id": goal.goal_id,
                "step_id": step_id,
                "week_number": week_number,
                "week_start_date": start_date.isoformat(),
                "week_end_date": end_date.isoformat(),
                "focus_status": "active",
                "selected_at": occurred_at,
                "updated_at": occurred_at,
            }
        )
        return self._send_simple_response(
            user,
            participant=participant,
            text=(
                f"Фокус недели {week_number} "
                f"(с {_format_date(start_date)} по {_format_date(end_date)}) сохранён: "
                f"Шаг {selected_step.step_number}"
            ),
            flow="idle",
            step="weekly_focus_saved",
            occurred_at=occurred_at,
        )

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
                buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON),
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
            focus = self.sheets.find_weekly_focus(
                participant_id,
                week_number=current_challenge_week_number(datetime.fromisoformat(occurred_at)),
            )
            return self._send_simple_response(
                user,
                participant=participant,
                text=format_planned_steps_view(steps, focus_step_id=_focus_step_id(focus)),
                flow="view_steps",
                step="render",
                occurred_at=occurred_at,
                buttons=_step_action_buttons(steps),
                parse_mode=TELEGRAM_HTML_PARSE_MODE,
            )

        if normalized_action is MenuAction.VIEW_PROGRESS:
            weekly_history = [
                _weekly_status_from_row(row)
                for row in self.sheets.list_weekly_status_history(participant_id)
            ]
            return self._send_simple_response(
                user,
                participant=participant,
                text=format_progress_view(
                    steps=steps,
                    weekly_history=weekly_history,
                    closed_week_number=closed_challenge_week_count(datetime.fromisoformat(occurred_at)),
                ),
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
        focus_response = self._maybe_prompt_weekly_focus(user, participant=participant, occurred_at=occurred_at)
        if focus_response is not None:
            return focus_response

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
        buttons: tuple[object, ...] = (),
        parse_mode: str | None = None,
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons, parse_mode=parse_mode)
        self.dialog_states.upsert(
            _dialog_state_for(
                user=user,
                participant=participant,
                flow=flow,
                step=step,
                occurred_at=occurred_at,
            )
        )
        self.main_bot.send_message(chat_id=user.chat_id, text=text, buttons=buttons, parse_mode=parse_mode)
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

    def _send_consent_response(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        occurred_at: str,
    ) -> FlowResponse:
        response = FlowResponse(
            chat_id=user.chat_id,
            text=CONSENT_TEXT,
            buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON),
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

    def _maybe_prompt_weekly_focus(
        self,
        user: TelegramUserContext,
        *,
        participant: SheetRow,
        occurred_at: str,
    ) -> FlowResponse | None:
        participant_id = _string_value(participant.get("participant_id"))
        goal_row = self.sheets.get_active_goal(participant_id)
        if goal_row is None:
            return None

        goal = _goal_from_row(goal_row)
        now = datetime.fromisoformat(occurred_at)
        if not is_working_week(now):
            return None

        week_number = current_challenge_week_number(now)
        if self.sheets.find_weekly_focus(participant_id, week_number=week_number) is not None:
            return None

        steps = [_planned_step_from_row(row) for row in self.sheets.list_planned_steps(participant_id, goal.goal_id)]
        open_steps = [step for step in steps if step.step_status != "closed"]
        if not open_steps:
            return None

        start_date, end_date = challenge_week_date_range(now)
        text = "\n".join(
            (
                f"Неделя {week_number}: с {_format_date(start_date)} по {_format_date(end_date)}.",
                "",
                "Выбери обязательный фокус недели.",
            )
        )
        return self._send_simple_response(
            user,
            participant=participant,
            text=text,
            flow="idle",
            step="weekly_focus",
            occurred_at=occurred_at,
            buttons=_weekly_focus_buttons(open_steps),
        )

    def _participant_for_current_flow(self, telegram_id: int) -> SheetRow | None:
        flow = self._active_registration_flow()
        if flow is not None:
            flow_id = _optional_string_value(flow.get("flow_id"))
            if flow_id:
                participant = self.sheets.find_participant_in_flow(flow_id, telegram_id)
                if participant is not None:
                    return participant
                return None
        return self.sheets.find_participant_by_telegram_id(telegram_id)

    def _active_registration_flow(self) -> SheetRow | None:
        gateway = self.registration_flows or self.sheets
        return gateway.get_active_challenge_flow()

    def _handle_registration_start(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        if self.registration_drafts is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)
        flow = self._active_registration_flow()
        if flow is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)
        now = datetime.fromisoformat(occurred_at)
        opens_at, closes_at = _registration_window(flow)
        if now < opens_at:
            return self._send_registration_response(user, "Регистрация в поток ещё не открыта.")
        if now > closes_at:
            self.registration_drafts.clear(user.telegram_id)
            self.dialog_states.clear(user.telegram_id)
            return self._send_registration_response(user, "Данный поток уже набран")

        draft = self.registration_drafts.get(user.telegram_id)
        flow_id = _string_value(flow.get("flow_id"))
        if draft is None:
            self.main_bot.send_message(
                chat_id=user.chat_id,
                text="Привет! Ты правильно попал — это бот проекта «Смерть иллюзий».",
            )
            return self._send_registration_response(
                user,
                CONSENT_TEXT,
                buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON),
            )
        if draft.flow_id != flow_id:
            self.registration_drafts.clear(user.telegram_id)
            self.dialog_states.clear(user.telegram_id)
            return self._handle_registration_start(user, occurred_at=occurred_at)
        return self._resume_registration(user, draft=draft, occurred_at=occurred_at)

    def _resume_registration(
        self,
        user: TelegramUserContext,
        *,
        draft: RegistrationDraft,
        occurred_at: str,
    ) -> FlowResponse:
        if draft.consent_given_at is None:
            step, text = "awaiting_consent", CONSENT_TEXT
            buttons: tuple[object, ...] = (CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON)
        elif draft.first_name is None:
            step, text, buttons = "awaiting_first_name", "Как тебя зовут? Напиши только имя.", ()
        elif draft.last_name is None:
            step, text, buttons = "awaiting_last_name", "Напиши фамилию.", ()
        elif draft.captain_id is None:
            return self._show_registration_captains(user, draft=draft, occurred_at=occurred_at)
        else:
            return self.select_registration_captain(
                user,
                captain_id=draft.captain_id,
                occurred_at=occurred_at,
            )
        self._set_registration_state(user, step=step, draft=draft, occurred_at=occurred_at)
        return self._send_registration_response(user, text, buttons=buttons)

    def _accept_registration_consent(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        flow = self._active_registration_flow()
        if self.registration_drafts is None or flow is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)
        opens_at, closes_at = _registration_window(flow)
        now = datetime.fromisoformat(occurred_at)
        if now < opens_at or now > closes_at:
            return self._send_registration_response(user, "Данный поток уже набран")
        draft = self.registration_drafts.get(user.telegram_id)
        if draft is None:
            draft = RegistrationDraft(
                telegram_id=user.telegram_id,
                flow_id=_string_value(flow.get("flow_id")),
                consent_given_at=occurred_at,
                created_at=occurred_at,
                updated_at=occurred_at,
                expires_at=closes_at.isoformat(),
            )
            self.registration_drafts.save(draft)
        else:
            draft = self._registration_repository().update(
                user.telegram_id,
                consent_given_at=occurred_at,
                updated_at=occurred_at,
            )
        self._set_registration_state(user, step="awaiting_first_name", draft=draft, occurred_at=occurred_at)
        return self._send_registration_response(user, "Как тебя зовут? Напиши только имя.")

    def _show_registration_captains(
        self,
        user: TelegramUserContext,
        *,
        draft: RegistrationDraft,
        occurred_at: str,
    ) -> FlowResponse:
        captains = [
            row
            for row in self.sheets.list_participants()
            if row.get("flow_id") == draft.flow_id
            and row.get("role") == "captain"
            and str(row.get("status", "active")) != "dropped"
            and self._captain_for_flow(draft.flow_id, str(row.get("participant_id", ""))) is not None
        ]
        buttons = tuple(
            TelegramInlineButton(_participant_name(captain), f"registration:captain:{captain['participant_id']}")
            for captain in captains
            if captain.get("participant_id")
        )
        if not buttons:
            return self._handle_missing_registration_data(user, draft=draft, occurred_at=occurred_at)
        self._set_registration_state(user, step="awaiting_captain", draft=draft, occurred_at=occurred_at)
        return self._send_registration_response(user, "Выбери капитана своей команды.", buttons=buttons)

    def _captain_for_flow(self, flow_id: str, captain_id: str) -> SheetRow | None:
        captain = self.sheets.get_participant(captain_id)
        if captain is None or captain.get("flow_id") != flow_id or captain.get("role") != "captain":
            return None
        if str(captain.get("status", "active")) != "active" or not _consent_is_given(captain):
            return None
        team_id = _optional_string_value(captain.get("team_id"))
        team = next(
            (
                row
                for row in self.sheets.list_teams()
                if row.get("flow_id") == flow_id
                and row.get("team_id") == team_id
                and row.get("captain_id") == captain_id
                and _truthy(row.get("is_active"))
            ),
            None,
        )
        if team is None:
            return None
        return captain

    def _valid_registration_draft(
        self,
        user: TelegramUserContext,
        *,
        occurred_at: str,
    ) -> RegistrationDraft:
        draft = self._registration_repository().get(user.telegram_id)
        active_flow = self._active_registration_flow()
        active_flow_id = _optional_string_value(active_flow.get("flow_id")) if active_flow else None
        now = datetime.fromisoformat(occurred_at)
        opens_at, closes_at = _registration_window(active_flow) if active_flow else (None, None)
        expired = (
            draft is not None
            and (
                opens_at is None
                or closes_at is None
                or now < opens_at
                or now > closes_at
                or datetime.fromisoformat(draft.expires_at) != closes_at
            )
        )
        wrong_flow = draft is not None and draft.flow_id != active_flow_id
        if draft is None or expired or wrong_flow:
            if draft is not None:
                self._registration_repository().clear(user.telegram_id)
                self.dialog_states.clear(user.telegram_id)
            raise RegistrationClosedError("Registration window is closed")
        return draft

    def _registration_repository(self) -> RegistrationDraftRepository:
        if self.registration_drafts is None:
            raise RuntimeError("Registration repository is not configured")
        return self.registration_drafts

    def _set_registration_state(
        self,
        user: TelegramUserContext,
        *,
        step: str,
        draft: RegistrationDraft,
        occurred_at: str,
    ) -> None:
        self.dialog_states.upsert(
            DialogState(
                telegram_id=user.telegram_id,
                participant_id=None,
                role=None,
                flow="registration",
                step=step,
                started_at=draft.created_at,
                updated_at=occurred_at,
                expires_at=draft.expires_at,
            )
        )

    def _send_registration_response(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        buttons: tuple[object, ...] = (),
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)
        self.main_bot.send_message(chat_id=user.chat_id, text=text, buttons=buttons)
        return response

    def _handle_missing_registration_data(
        self,
        user: TelegramUserContext,
        *,
        draft: RegistrationDraft,
        occurred_at: str,
    ) -> FlowResponse:
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=f"registration_captains_missing flow_id={draft.flow_id} occurred_at={occurred_at}",
            recipients=(),
        )
        return self._send_registration_response(user, "Регистрация временно недоступна. Сообщи администратору.")

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


def _flow_timestamp(flow: SheetRow, field: str) -> datetime:
    value = _optional_string_value(flow.get(field))
    if not value:
        raise ValueError(f"Active flow is missing {field}")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Active flow timestamp has no timezone: {field}")
    return parsed


def _registration_window(flow: SheetRow) -> tuple[datetime, datetime]:
    kickoff = _flow_timestamp(flow, "kickoff_meeting_at")
    opens_at = _flow_timestamp(flow, "registration_opens_at")
    closes_at = _flow_timestamp(flow, "registration_closes_at")
    expected_offset = 5 * 60 * 60
    if int(opens_at.utcoffset().total_seconds()) != expected_offset:
        raise ValueError("Registration window must use Asia/Yekaterinburg UTC offset")
    if opens_at != kickoff or closes_at - opens_at != timedelta(days=7):
        raise ValueError("Registration window must start at kickoff and last exactly seven days")
    return opens_at, closes_at


def _participant_name(participant: SheetRow) -> str:
    full_name = _optional_string_value(participant.get("full_name"))
    if full_name:
        return full_name
    return " ".join(
        value
        for value in (
            _optional_string_value(participant.get("first_name")),
            _optional_string_value(participant.get("last_name")),
        )
        if value
    )


def _registration_participant_id(flow_id: str, telegram_id: int) -> str:
    digest = sha256(f"{flow_id}:{telegram_id}".encode("utf-8")).hexdigest()[:12].upper()
    return f"P{digest}"


def _registration_success_text(participant: SheetRow, captain: SheetRow, flow: SheetRow) -> str:
    first_name = _optional_string_value(participant.get("first_name")) or "Участник"
    captain_name = _participant_name(captain) or "не указан"
    lines = [
        f"{first_name}, ты успешно зарегистрирован в проекте «Смерть иллюзий».",
        f"Твой капитан — {captain_name}.",
    ]
    dates = (
        ("Постановка цели", "goal_setup_start_date", "goal_setup_end_date"),
        ("Формирование шагов", "steps_setup_start_date", "steps_setup_end_date"),
        ("Рабочие недели", "week_01_start_date", "week_08_end_date"),
    )
    schedule = []
    for label, start_field, end_field in dates:
        start = _optional_string_value(flow.get(start_field))
        end = _optional_string_value(flow.get(end_field))
        if start and end:
            schedule.append(f"{label}: {_short_date(start)}–{_short_date(end)}")
    if schedule:
        lines.extend(("", "Краткое расписание:", *schedule))
    return "\n".join(lines)


def _short_date(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%d.%m.%Y")


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "да"}


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
    return (
        "unknown_telegram_user "
        f"telegram_id={user.telegram_id} "
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
    status_code = str(row.get("status_code") or "")
    status_symbol = "⬛" if status_code == "gray" else str(row.get("status_symbol") or "")
    return WeeklyStatus(
        week_number=_int_value(row.get("week_number")),
        status_symbol=status_symbol,
        status_code=status_code,
        submitted_at=_optional_string_value(row.get("submitted_at")),
    )


def _step_action_buttons(steps: list[PlannedStep]) -> tuple[TelegramInlineButton, ...]:
    return tuple(
        TelegramInlineButton(
            text=_step_action_button_text(step),
            callback_data=f"{_step_action_callback_prefix(step)}{step.step_id}",
        )
        for step in sorted(steps, key=lambda item: item.step_number)
    )


def _weekly_focus_buttons(steps: list[PlannedStep]) -> tuple[TelegramInlineButton, ...]:
    return tuple(
        TelegramInlineButton(
            text=_step_button_text(step),
            callback_data=f"{WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX}{step.step_id}",
        )
        for step in sorted(steps, key=lambda item: item.step_number)
    )


def _step_button_text(step: PlannedStep) -> str:
    return f"Шаг {step.step_number}. {_short_step_title(step.step_title)}"


def _step_action_button_text(step: PlannedStep) -> str:
    action = WEEKLY_REPORT_EDIT_STEP_BUTTON if step.step_status == "closed" else WEEKLY_REPORT_START_STEP_BUTTON
    return f"{_step_button_text(step)} - {action}"


def _step_action_callback_prefix(step: PlannedStep) -> str:
    if step.step_status == "closed":
        return WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX
    return WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX


def _focus_step_id(row: SheetRow | None) -> str | None:
    return _optional_string_value(row.get("step_id")) if row is not None else None


def _step_by_id(steps: list[PlannedStep], step_id: str) -> PlannedStep:
    for step in steps:
        if step.step_id == step_id:
            return step
    raise ValueError("selected step is not available")


def _weekly_focus_id(participant_id: str, week_number: int) -> str:
    return f"WF:{participant_id}:week-{week_number:02d}"


def _format_date(value) -> str:
    return value.strftime("%d.%m.%Y")


def _onboarding_intro_text() -> str:
    return "\n\n".join(
        (
            CONSENT_ACCEPTED_INTRO_TEXT,
            CHALLENGE_STAGES_TEXT,
            GOAL_SETUP_INTRO_TEXT,
        )
    )


def _short_step_title(title: str, *, limit: int = 42) -> str:
    normalized = " ".join(title.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3].rstrip()}..."


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
