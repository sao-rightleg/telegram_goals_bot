"""Participant weekly report service flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.bot.clients import BotClient
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
    WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_DUPLICATE_TEXT,
    WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_LATE_TEXT,
    build_weekly_report_status_buttons,
)
from app.scheduler.calendar import current_challenge_week_number, is_weekly_report_open
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.weekly_report_models import WeeklyReportStatus
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


@dataclass(frozen=True)
class WeeklyReportService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    drafts: WeeklyReportDraftRepository

    def start_report(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        participant, participant_id, team_id, goal, week_number = context
        steps = self.sheets.list_planned_steps(participant_id, _string_value(goal.get("goal_id")))
        open_steps = [row for row in steps if row.get("step_status") != "closed"]
        if not open_steps:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="planned_steps",
                occurred_at=_occurred_at(now),
            )

        self.drafts.create_draft(
            draft_id=_draft_id(participant_id, week_number),
            telegram_id=user.telegram_id,
            participant_id=participant_id,
            team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")),
            week_number=week_number,
            occurred_at=_occurred_at(now),
        )
        return self._send(
            user,
            text=_format_start_text(open_steps),
            buttons=build_weekly_report_status_buttons(),
        )

    def select_status(
        self,
        user: TelegramUserContext,
        status: WeeklyReportStatus,
        *,
        now: datetime,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")

        if status is WeeklyReportStatus.RED:
            self.drafts.update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
            return self._send(user, text="Что помешало сделать победу недели?")

        self.drafts.update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
        return self._send(user, text=_step_required_text(status))

    def select_steps(
        self,
        user: TelegramUserContext,
        step_ids: list[str] | tuple[str, ...],
        *,
        now: datetime,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        _participant, participant_id, _team_id, goal, _week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")

        status = _status_from_code(draft.status_code) or WeeklyReportStatus.GREEN
        if status is WeeklyReportStatus.RED:
            self.drafts.update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
            return self._send(user, text="Что помешало сделать победу недели?")

        valid_steps = _valid_step_ids(
            self.sheets.list_planned_steps(participant_id, _string_value(goal.get("goal_id"))),
            require_open=status is WeeklyReportStatus.GREEN,
        )
        selected_step_ids = [step_id for step_id in step_ids if step_id in valid_steps]
        if not selected_step_ids or len(selected_step_ids) != len(set(step_ids)):
            return self._send(user, text=_step_required_text(status))

        self.drafts.update_status_and_steps(
            user.telegram_id,
            status,
            selected_step_ids,
            occurred_at=_occurred_at(now),
        )
        return self._send(user, text=_text_prompt(status))

    def _resolve_context(
        self,
        user: TelegramUserContext,
        *,
        now: datetime,
    ) -> tuple[SheetRow, str, str, SheetRow, int] | FlowResponse:
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        occurred_at = _occurred_at(now)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)

        if not _consent_is_given(participant):
            return self._send(user, text=CONSENT_TEXT, buttons=(CONSENT_ACCEPT_BUTTON,))

        if not is_weekly_report_open(now):
            return self._send(user, text=WEEKLY_REPORT_LATE_TEXT)

        participant_id = _string_value(participant.get("participant_id"))
        team_id = _optional_string_value(participant.get("team_id"))
        if team_id is None:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="team_id",
                occurred_at=occurred_at,
            )

        week_number = current_challenge_week_number(now)
        if self.sheets.find_weekly_report(participant_id, week_number=week_number) is not None:
            return self._send(user, text=WEEKLY_REPORT_DUPLICATE_TEXT)

        goal = self.sheets.get_active_goal(participant_id)
        if goal is None:
            return self._handle_missing_data(
                user,
                participant=participant,
                missing_type="active_goal",
                occurred_at=occurred_at,
            )

        return participant, participant_id, team_id, goal, week_number

    def _send(
        self,
        user: TelegramUserContext,
        *,
        text: str,
        buttons: tuple[str, ...] = (),
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)
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
        response = self._send(user, text=MISSING_DATA_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_missing_data_error_text(user, participant, missing_type, occurred_at),
            recipients=(),
        )
        return response

    def _handle_unknown_user(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        response = self._send(user, text=UNKNOWN_USER_TEXT)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=_unknown_user_error_text(user, occurred_at),
            recipients=(),
        )
        return response


def _format_start_text(open_steps: list[SheetRow]) -> str:
    lines = ["На этой неделе у тебя остались незакрытые шаги:"]
    lines.extend(
        f"{_int_value(row.get('step_number'))}. {str(row.get('step_title') or '')}"
        for row in sorted(open_steps, key=lambda item: _int_value(item.get("step_number")))
    )
    lines.append("Выбери статус недели.")
    return "\n".join(lines)


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


def _draft_id(participant_id: str, week_number: int) -> str:
    return f"weekly-report:{participant_id}:week-{week_number:02d}"


def _occurred_at(now: datetime) -> str:
    return now.isoformat()


def _consent_is_given(participant: SheetRow) -> bool:
    value = participant.get("consent_given")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "да"}
    return False


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


def _string_value(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("string value is required")
    return value


def _optional_string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip():
        return int(value)
    raise ValueError("integer value is required")
