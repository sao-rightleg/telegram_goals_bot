"""Captain-only service flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.bot.clients import BotClient
from app.bot.messages import (
    CAPTAIN_DROPPED_PARTICIPANT_TEXT,
    CAPTAIN_EMPTY_REPORT_TEXT,
    CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT,
    CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT,
    CAPTAIN_MANUAL_REPORT_LATE_TEXT,
    CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT,
    CAPTAIN_NO_TEAM_MEMBERS_TEXT,
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_TEAM_TITLE_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
    WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT,
    build_weekly_report_status_buttons,
    format_captain_team_member_line,
)
from app.scheduler.calendar import current_challenge_week_number, is_weekly_report_open
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.weekly_report_models import WeeklyReportStatus
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.weekly_report_drafts import WeeklyReportDraft, WeeklyReportDraftRepository


@dataclass(frozen=True)
class CaptainService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    drafts: WeeklyReportDraftRepository | None = None

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

    def start_manual_report(
        self,
        user: TelegramUserContext,
        target_participant_id: str,
        *,
        now: datetime,
    ) -> FlowResponse:
        context = self._resolve_manual_context(user, target_participant_id, now=now)
        if isinstance(context, FlowResponse):
            return context

        captain, captain_id, target, target_id, team_id, goal, week_number = context
        open_steps = [
            row
            for row in self.sheets.list_planned_steps(target_id, _string_value(goal.get("goal_id")))
            if row.get("step_status") != "closed"
        ]
        if not open_steps:
            return self._handle_missing_data(
                user,
                participant=target,
                missing_type="planned_steps",
                occurred_at=_occurred_at(now),
            )

        self._drafts().create_captain_manual_draft(
            draft_id=_draft_id(target_id, week_number),
            telegram_id=user.telegram_id,
            captain_participant_id=captain_id,
            target_participant_id=target_id,
            team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")),
            week_number=week_number,
            occurred_at=_occurred_at(now),
        )
        return self._send_response(
            user,
            text=_format_manual_start_text(target, open_steps),
            buttons=build_weekly_report_status_buttons(),
        )

    def select_status(
        self,
        user: TelegramUserContext,
        status: WeeklyReportStatus,
        *,
        now: datetime,
    ) -> FlowResponse:
        draft = self._active_captain_draft(user)
        context = self._resolve_manual_context(user, draft.participant_id, now=now)
        if isinstance(context, FlowResponse):
            return context

        self._drafts().update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
        if status is WeeklyReportStatus.RED:
            return self._send_response(user, text=_text_prompt(status))
        return self._send_response(user, text=_step_required_text(status))

    def select_steps(
        self,
        user: TelegramUserContext,
        step_ids: list[str] | tuple[str, ...],
        *,
        now: datetime,
    ) -> FlowResponse:
        draft = self._active_captain_draft(user)
        context = self._resolve_manual_context(user, draft.participant_id, now=now)
        if isinstance(context, FlowResponse):
            return context

        _captain, _captain_id, _target, target_id, _team_id, goal, _week_number = context
        status = _status_from_code(draft.status_code) or WeeklyReportStatus.GREEN
        if status is WeeklyReportStatus.RED:
            self._drafts().update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
            return self._send_response(user, text=_text_prompt(status))

        valid_steps = _valid_step_ids(
            self.sheets.list_planned_steps(target_id, _string_value(goal.get("goal_id"))),
            require_open=status is WeeklyReportStatus.GREEN,
        )
        selected_step_ids = [step_id for step_id in step_ids if step_id in valid_steps]
        if not selected_step_ids or len(selected_step_ids) != len(set(step_ids)):
            return self._send_response(user, text=_step_required_text(status))

        self._drafts().update_status_and_steps(
            user.telegram_id,
            status,
            selected_step_ids,
            occurred_at=_occurred_at(now),
        )
        return self._send_response(user, text=_text_prompt(status))

    def add_text_message(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        draft = self._active_captain_draft(user)
        context = self._resolve_manual_context(user, draft.participant_id, now=now)
        if isinstance(context, FlowResponse):
            return context

        self._drafts().append_text_message(
            user.telegram_id,
            text,
            occurred_at=_occurred_at(now),
            telegram_message_id=telegram_message_id,
        )
        return self._send_response(user, text="Текст добавлен. Можно отправить ещё или нажать «✅ Готово».")

    def finalize_manual_report(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        draft = self._active_captain_draft(user)
        context = self._resolve_manual_context(user, draft.participant_id, now=now)
        if isinstance(context, FlowResponse):
            return context

        _captain, captain_id, _target, target_id, team_id, goal, week_number = context
        status = _status_from_code(draft.status_code)
        if status is None:
            return self._send_response(user, text=WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT)
        if status in {WeeklyReportStatus.GREEN, WeeklyReportStatus.BLUE}:
            if not draft.selected_step_ids or not self._selected_steps_are_valid(draft, status, goal):
                return self._send_response(user, text=_step_required_text(status))
        if not draft.report_text.strip():
            return self._send_response(user, text=CAPTAIN_EMPTY_REPORT_TEXT)

        goal_id = _string_value(goal.get("goal_id"))
        submitted_at = _occurred_at(now)
        weekly_report_id = _weekly_report_id(target_id, week_number)
        self.sheets.append_weekly_report(
            {
                "weekly_report_id": weekly_report_id,
                "participant_id": target_id,
                "team_id": team_id,
                "goal_id": goal_id,
                "week_number": week_number,
                "status_code": status.code,
                "status_symbol": status.symbol,
                "score": status.score,
                "report_text": draft.report_text,
                "transcription_text": _voice_transcription_text(draft),
                "audio_file_path": _voice_audio_file_path(draft),
                "audio_deleted_at": "",
                "submitted_at": submitted_at,
                "submitted_by_id": captain_id,
                "submitted_by_role": "captain",
                "flow_source": "captain_manual",
            }
        )
        if status in {WeeklyReportStatus.GREEN, WeeklyReportStatus.BLUE}:
            relation_status = "closed" if status is WeeklyReportStatus.GREEN else "partial"
            for step_id in draft.selected_step_ids:
                self.sheets.append_weekly_report_step(
                    {
                        "weekly_report_step_id": _weekly_report_step_id(weekly_report_id, step_id),
                        "weekly_report_id": weekly_report_id,
                        "participant_id": target_id,
                        "goal_id": goal_id,
                        "step_id": step_id,
                        "week_number": week_number,
                        "relation_status": relation_status,
                        "created_at": submitted_at,
                    }
                )
        if status is WeeklyReportStatus.GREEN:
            self.sheets.close_planned_steps(
                target_id,
                goal_id,
                draft.selected_step_ids,
                closed_week_number=week_number,
                closed_report_id=weekly_report_id,
                closed_at=submitted_at,
            )

        self._drafts().clear_draft(user.telegram_id)
        return self._send_response(user, text=CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT)

    def _send_response(
        self,
        user: TelegramUserContext,
        *,
        text: str,
        buttons: tuple[str, ...] = (),
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)
        self.main_bot.send_message(chat_id=user.chat_id, text=text)
        return response

    def _resolve_manual_context(
        self,
        user: TelegramUserContext,
        target_participant_id: str,
        *,
        now: datetime,
    ) -> tuple[SheetRow, str, SheetRow, str, str, SheetRow, int] | FlowResponse:
        captain_context = self._resolve_captain(user, occurred_at=_occurred_at(now))
        if isinstance(captain_context, FlowResponse):
            return captain_context

        captain, captain_id, team_id = captain_context
        if not is_weekly_report_open(now):
            return self._send_response(user, text=CAPTAIN_MANUAL_REPORT_LATE_TEXT)

        target = self.sheets.get_participant(target_participant_id)
        if target is None:
            return self._send_response(user, text=CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT)

        target_id = _string_value(target.get("participant_id"))
        target_team_id = _optional_string_value(target.get("team_id"))
        if target_team_id != team_id:
            return self._send_response(user, text=CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT)
        if _is_dropped(target):
            return self._send_response(user, text=CAPTAIN_DROPPED_PARTICIPANT_TEXT)

        week_number = current_challenge_week_number(now)
        if self.sheets.find_weekly_report(target_id, week_number=week_number) is not None:
            return self._send_response(user, text=CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT)

        goal = self.sheets.get_active_goal(target_id)
        if goal is None:
            return self._handle_missing_data(
                user,
                participant=target,
                missing_type="active_goal",
                occurred_at=_occurred_at(now),
            )

        return captain, captain_id, target, target_id, team_id, goal, week_number

    def _resolve_captain(
        self,
        user: TelegramUserContext,
        *,
        occurred_at: str,
    ) -> tuple[SheetRow, str, str] | FlowResponse:
        captain = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if captain is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)
        if not _consent_is_given(captain):
            return self._send_response(user, text=CONSENT_TEXT, buttons=(CONSENT_ACCEPT_BUTTON,))
        if _role(captain) != "captain":
            return self._send_response(user, text=CAPTAIN_ONLY_TEXT)

        captain_id = _string_value(captain.get("participant_id"))
        team_id = _optional_string_value(captain.get("team_id"))
        if team_id is None:
            return self._handle_missing_data(
                user,
                participant=captain,
                missing_type="team_id",
                occurred_at=occurred_at,
            )
        return captain, captain_id, team_id

    def _selected_steps_are_valid(
        self,
        draft: WeeklyReportDraft,
        status: WeeklyReportStatus,
        goal: SheetRow,
    ) -> bool:
        valid_steps = _valid_step_ids(
            self.sheets.list_planned_steps(draft.participant_id, _string_value(goal.get("goal_id"))),
            require_open=status is WeeklyReportStatus.GREEN,
        )
        return bool(draft.selected_step_ids) and set(draft.selected_step_ids).issubset(valid_steps)

    def _active_captain_draft(self, user: TelegramUserContext) -> WeeklyReportDraft:
        draft = self._drafts().get_active_draft(user.telegram_id)
        if draft is None or draft.flow_source != "captain_manual":
            raise KeyError(f"Active captain manual report draft not found for telegram_id={user.telegram_id}")
        return draft

    def _drafts(self) -> WeeklyReportDraftRepository:
        if self.drafts is None:
            raise RuntimeError("Captain manual report flow requires a draft repository")
        return self.drafts

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


def _format_manual_start_text(target: SheetRow, open_steps: list[SheetRow]) -> str:
    lines = [f"Отчёт за участника: {_display_name(target)}", "Открытые шаги:"]
    lines.extend(
        f"{_int_value(row.get('step_number'))}. {str(row.get('step_title') or '')}"
        for row in sorted(open_steps, key=lambda item: _int_value(item.get("step_number")))
    )
    lines.append("Выбери статус недели.")
    return "\n".join(lines)


def _team_member_sort_key(participant: SheetRow) -> tuple[str, str]:
    display_name = (
        _optional_string_value(participant.get("full_name"))
        or _optional_string_value(participant.get("display_name"))
        or _optional_string_value(participant.get("name"))
        or ""
    )
    participant_id = _optional_string_value(participant.get("participant_id")) or ""
    return (display_name.lower(), participant_id)


def _display_name(participant: SheetRow) -> str:
    return (
        _optional_string_value(participant.get("full_name"))
        or _optional_string_value(participant.get("display_name"))
        or _optional_string_value(participant.get("name"))
        or "Участник без имени"
    )


def _valid_step_ids(rows: list[SheetRow], *, require_open: bool) -> set[str]:
    return {
        _string_value(row.get("step_id"))
        for row in rows
        if not require_open or row.get("step_status") != "closed"
    }


def _status_from_code(value: str | None) -> WeeklyReportStatus | None:
    for status in WeeklyReportStatus:
        if status.code == value:
            return status
    return None


def _step_required_text(status: WeeklyReportStatus) -> str:
    if status is WeeklyReportStatus.BLUE:
        return WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT
    return WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT


def _text_prompt(status: WeeklyReportStatus) -> str:
    if status is WeeklyReportStatus.BLUE:
        return "Что получилось сделать частично?"
    if status is WeeklyReportStatus.RED:
        return "Что помешало сделать победу недели?"
    return "Что именно ты сделал?"


def _voice_transcription_text(draft: WeeklyReportDraft) -> str:
    return "\n".join(
        attachment.transcription_text for attachment in draft.voice_attachments if attachment.transcription_text
    )


def _voice_audio_file_path(draft: WeeklyReportDraft) -> str:
    return "\n".join(attachment.local_file_path for attachment in draft.voice_attachments)


def _draft_id(participant_id: str, week_number: int) -> str:
    return f"captain-manual:{participant_id}:week-{week_number:02d}"


def _weekly_report_id(participant_id: str, week_number: int) -> str:
    return f"WR:{participant_id}:week-{week_number:02d}"


def _weekly_report_step_id(weekly_report_id: str, step_id: str) -> str:
    return f"WRS:{weekly_report_id}:{step_id}"


def _occurred_at(now: datetime) -> str:
    return now.isoformat()


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


def _is_dropped(participant: SheetRow) -> bool:
    value = participant.get("status")
    return isinstance(value, str) and value.strip().lower() == "dropped"


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


def _string_value(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("string value is required")
    return value


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError("integer value is required")
