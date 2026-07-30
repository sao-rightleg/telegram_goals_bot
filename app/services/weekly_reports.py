"""Participant weekly report service flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.bot.clients import BotClient, TelegramInlineButton
from app.bot.menus import WEEKLY_REPORT_DONE_CALLBACK
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
    WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_DUPLICATE_TEXT,
    WEEKLY_REPORT_EMPTY_TEXT,
    WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_LATE_TEXT,
    WEEKLY_REPORT_RECOVERY_TEXT,
    WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT,
    build_weekly_report_status_buttons,
    get_weekly_report_success_text,
)
from app.scheduler.calendar import current_challenge_week_number, is_weekly_report_open
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.voice_messages import VoiceMessageInput, VoiceMessageService
from app.services.weekly_report_models import WeeklyReportStatus
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


@dataclass(frozen=True)
class WeeklyReportService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    drafts: WeeklyReportDraftRepository
    voice_messages: VoiceMessageService | None = None

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

    def start_report_for_step(
        self,
        user: TelegramUserContext,
        *,
        step_id: str,
        now: datetime,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        participant, participant_id, team_id, goal, week_number = context
        goal_id = _string_value(goal.get("goal_id"))
        steps = self.sheets.list_planned_steps(participant_id, goal_id)
        open_steps = [row for row in steps if row.get("step_status") != "closed"]
        valid_open_step_ids = {_string_value(row.get("step_id")) for row in open_steps}
        if step_id not in valid_open_step_ids:
            return self._send(user, text=WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT)

        self.drafts.create_draft(
            draft_id=_draft_id(participant_id, week_number),
            telegram_id=user.telegram_id,
            participant_id=participant_id,
            team_id=team_id,
            goal_id=goal_id,
            week_number=week_number,
            occurred_at=_occurred_at(now),
        )
        self.drafts.preselect_steps(user.telegram_id, [step_id], occurred_at=_occurred_at(now))
        return self._send(
            user,
            text=_format_step_start_text(_step_by_id(open_steps, step_id)),
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

        _participant, participant_id, _team_id, goal, _week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")

        if status is WeeklyReportStatus.RED:
            self.drafts.update_status_and_steps(user.telegram_id, status, [], occurred_at=_occurred_at(now))
            return self._send(user, text="Что помешало сделать победу недели?")

        selected_step_ids = _valid_selected_step_ids(
            self.sheets.list_planned_steps(participant_id, _string_value(goal.get("goal_id"))),
            draft.selected_step_ids,
            require_open=status is WeeklyReportStatus.GREEN,
        )
        self.drafts.update_status_and_steps(
            user.telegram_id,
            status,
            selected_step_ids,
            occurred_at=_occurred_at(now),
        )
        if selected_step_ids:
            return self._send(user, text=_text_prompt(status))
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

    def add_text_message(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        if self.drafts.get_active_draft(user.telegram_id) is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")

        self.drafts.append_text_message(
            user.telegram_id,
            text,
            occurred_at=_occurred_at(now),
            telegram_message_id=telegram_message_id,
        )
        return self._send(
            user,
            text="Текст добавлен. Можно отправить ещё или нажать «✅ Готово».",
            buttons=_weekly_report_text_buttons(),
        )

    def add_voice_message(
        self,
        user: TelegramUserContext,
        *,
        telegram_file_id: str,
        duration_seconds: int,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        if self.drafts.get_active_draft(user.telegram_id) is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        if self.voice_messages is None:
            return self.reject_voice_message(user, now=now)

        result = self.voice_messages.handle_voice(
            VoiceMessageInput(
                user=user,
                telegram_file_id=telegram_file_id,
                duration_seconds=duration_seconds,
                telegram_message_id=telegram_message_id,
                now=now,
            )
        )
        return self._send(user, text=result.text, buttons=_weekly_report_text_buttons())

    def reject_voice_message(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        return self._send(user, text=WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT)

    def recover_invalid_draft(
        self,
        user: TelegramUserContext,
        *,
        reason: str,
        now: datetime,
    ) -> FlowResponse:
        self.drafts.clear_draft(user.telegram_id)
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=(
                "invalid_weekly_report_draft "
                f"telegram_id={user.telegram_id} "
                f"reason={reason} "
                f"occurred_at={_occurred_at(now)}"
            ),
            recipients=(),
        )
        return self._send(user, text=WEEKLY_REPORT_RECOVERY_TEXT)

    def finalize_report(self, user: TelegramUserContext, *, now: datetime) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")

        status = _status_from_code(draft.status_code)
        if status is None:
            return self._send(user, text=WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT)
        if status in {WeeklyReportStatus.GREEN, WeeklyReportStatus.BLUE} and not draft.selected_step_ids:
            return self._send(user, text=_step_required_text(status))
        if not draft.report_text.strip():
            return self._send(user, text=WEEKLY_REPORT_EMPTY_TEXT)

        goal_id = _string_value(goal.get("goal_id"))
        submitted_at = _occurred_at(now)
        weekly_report_id = _weekly_report_id(participant_id, week_number)
        self.sheets.append_weekly_report(
            {
                "weekly_report_id": weekly_report_id,
                "participant_id": participant_id,
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
                "submitted_by_id": participant_id,
                "submitted_by_role": "participant",
                "flow_source": "participant_bot",
            }
        )
        if status in {WeeklyReportStatus.GREEN, WeeklyReportStatus.BLUE}:
            relation_status = "closed" if status is WeeklyReportStatus.GREEN else "partial"
            for step_id in draft.selected_step_ids:
                self.sheets.append_weekly_report_step(
                    {
                        "weekly_report_step_id": _weekly_report_step_id(weekly_report_id, step_id),
                        "weekly_report_id": weekly_report_id,
                        "participant_id": participant_id,
                        "goal_id": goal_id,
                        "step_id": step_id,
                        "week_number": week_number,
                        "relation_status": relation_status,
                        "created_at": submitted_at,
                    }
                )
        if status is WeeklyReportStatus.GREEN:
            self.sheets.close_planned_steps(
                participant_id,
                goal_id,
                draft.selected_step_ids,
                closed_week_number=week_number,
                closed_report_id=weekly_report_id,
                closed_at=submitted_at,
            )

        self.drafts.clear_draft(user.telegram_id)
        return self._send(user, text=get_weekly_report_success_text(status))

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
        buttons: tuple[object, ...] = (),
    ) -> FlowResponse:
        response = FlowResponse(chat_id=user.chat_id, text=text, buttons=buttons)
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


def _weekly_report_text_buttons() -> tuple[TelegramInlineButton, ...]:
    return (
        TelegramInlineButton(
            text="✅ Готово",
            callback_data=WEEKLY_REPORT_DONE_CALLBACK,
        ),
    )


def _format_step_start_text(step: SheetRow) -> str:
    return "\n".join(
        (
            "Выбран шаг:",
            f"{_int_value(step.get('step_number'))}. {str(step.get('step_title') or '')}",
            "Выбери статус недели.",
        )
    )


def _step_by_id(rows: list[SheetRow], step_id: str) -> SheetRow:
    for row in rows:
        if row.get("step_id") == step_id:
            return row
    raise ValueError("selected step is not available")


def _valid_step_ids(rows: list[SheetRow], *, require_open: bool) -> set[str]:
    return {
        _string_value(row.get("step_id"))
        for row in rows
        if not require_open or row.get("step_status") != "closed"
    }


def _valid_selected_step_ids(
    rows: list[SheetRow],
    selected_step_ids: tuple[str, ...],
    *,
    require_open: bool,
) -> list[str]:
    valid_step_ids = _valid_step_ids(rows, require_open=require_open)
    return [step_id for step_id in selected_step_ids if step_id in valid_step_ids]


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


def _voice_transcription_text(draft) -> str:
    return "\n".join(
        attachment.transcription_text for attachment in draft.voice_attachments if attachment.transcription_text
    )


def _voice_audio_file_path(draft) -> str:
    return "\n".join(attachment.local_file_path for attachment in draft.voice_attachments)


def _draft_id(participant_id: str, week_number: int) -> str:
    return f"weekly-report:{participant_id}:week-{week_number:02d}"


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
