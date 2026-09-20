"""Participant weekly report service flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.bot.clients import BotClient, TelegramInlineButton
from app.bot.menus import WEEKLY_REPORT_DONE_CALLBACK, WEEKLY_REPORT_METRIC_CALLBACK_PREFIX
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_DECLINE_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
    WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_EMPTY_TEXT,
    WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_LATE_TEXT,
    WEEKLY_REPORT_RECOVERY_TEXT,
    WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT,
    build_weekly_report_status_buttons,
    format_weekly_report_not_open_text,
    get_weekly_report_success_text,
)
from app.scheduler.calendar import (
    current_challenge_stage,
    current_challenge_week_number,
    is_weekly_report_open,
    working_weeks_start_date,
)
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.voice_messages import VoiceMessageInput, VoiceMessageService
from app.services.weekly_report_models import WeeklyReportStatus
from app.sheets.gateway import SheetRow, SheetsGateway
from app.storage.weekly_report_drafts import WeeklyReportDraft, WeeklyReportDraftRepository


@dataclass(frozen=True)
class WeeklyReportService:
    sheets: SheetsGateway
    main_bot: BotClient
    notification_router: NotificationRouter
    drafts: WeeklyReportDraftRepository
    voice_messages: VoiceMessageService | None = None
    active_flow_id: str | None = None

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
        if self.sheets.find_weekly_report_for_step_week(
            participant_id, step_id=step_id, week_number=week_number
        ) is not None:
            return self._send(user, text="По этому шагу отчёт уже сохранён. Нажми «Редактировать отчёт».")

        self.drafts.create_draft(
            draft_id=_draft_id(participant_id, week_number, step_id=step_id),
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
            buttons=_metric_status_buttons(),
        )

    def select_metric_result(
        self, user: TelegramUserContext, metric_status: str, *, now: datetime
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context
        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if (
            draft is None
            or len(draft.selected_step_ids) != 1
            or ":step-" not in draft.draft_id
            or _edit_report_id(draft.draft_id) is not None
        ):
            raise KeyError(f"Active step report draft not found for telegram_id={user.telegram_id}")
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")), week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)
        valid_ids = _valid_step_ids(
            self.sheets.list_planned_steps(participant_id, _string_value(goal.get("goal_id"))),
            require_open=True,
        )
        if draft.selected_step_ids[0] not in valid_ids:
            return self._send(user, text=WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT)
        status_by_metric = {
            "completed": WeeklyReportStatus.GREEN,
            "partial": WeeklyReportStatus.BLUE,
            "not_completed": WeeklyReportStatus.RED,
        }
        status = status_by_metric.get(metric_status)
        if status is None:
            raise ValueError("Unsupported metric status")
        self.drafts.select_metric(
            user.telegram_id, metric_status=metric_status,
            status=status, occurred_at=_occurred_at(now),
        )
        return self._send(
            user,
            text="Укажи фактический результат по метрике. Например: «Провёл 8 из 10 встреч».",
        )

    def start_edit_report_for_step(
        self,
        user: TelegramUserContext,
        *,
        step_id: str,
        now: datetime,
    ) -> FlowResponse:
        context = self._resolve_context(user, now=now)
        if isinstance(context, FlowResponse):
            return context

        _participant, participant_id, team_id, goal, week_number = context
        goal_id = _string_value(goal.get("goal_id"))
        report = self.sheets.find_weekly_report_for_step(participant_id, step_id=step_id)
        if report is None:
            return self._send(user, text="По этому шагу ещё нет отчёта. Нажми «Отчитаться».")

        report_id = _string_value(report.get("weekly_report_id"))
        self.drafts.create_draft(
            draft_id=_edit_draft_id(report_id),
            telegram_id=user.telegram_id,
            participant_id=participant_id,
            team_id=team_id,
            goal_id=goal_id,
            week_number=week_number,
            occurred_at=_occurred_at(now),
        )
        self.drafts.preselect_steps(user.telegram_id, [step_id], occurred_at=_occurred_at(now))
        self.drafts.update_status_and_steps(
            user.telegram_id,
            WeeklyReportStatus.GREEN,
            [step_id],
            occurred_at=_occurred_at(now),
        )
        return self._send(
            user,
            text="Отправь новый текст отчёта по этому шагу.",
            buttons=_weekly_report_text_buttons(),
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

        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")), week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)

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

        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        goal_id = _string_value(goal.get("goal_id"))
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=goal_id, week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)
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

        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")), week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)
        if _draft_has_duplicate_step_report(self.sheets, draft):
            return self._send(user, text="По этому шагу отчёт уже сохранён. Нажми «Редактировать отчёт».")

        self.drafts.append_text_message(
            user.telegram_id,
            text,
            occurred_at=_occurred_at(now),
            telegram_message_id=telegram_message_id,
        )
        return self._send(
            user,
            text="Текст добавлен. Можно отправить ещё или нажать «✅ Отчёт готов».",
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

        _participant, participant_id, team_id, goal, week_number = context
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=_string_value(goal.get("goal_id")), week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)
        if _draft_has_duplicate_step_report(self.sheets, draft):
            return self._send(user, text="По этому шагу отчёт уже сохранён. Нажми «Редактировать отчёт».")
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
        submitted_at = _occurred_at(now)
        self.drafts.recover_stale_finalization(
            user.telegram_id,
            stale_before=_occurred_at(now - timedelta(minutes=10)),
            occurred_at=submitted_at,
        )
        draft = self.drafts.get_active_draft(user.telegram_id)
        if draft is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={user.telegram_id}")
        goal_id = _string_value(goal.get("goal_id"))
        if not _draft_scope_matches(
            draft, participant_id=participant_id, team_id=team_id,
            goal_id=goal_id, week_number=week_number,
        ):
            return self.recover_invalid_draft(user, reason="scope_mismatch", now=now)

        status = _status_from_code(draft.status_code)
        if status is None:
            return self._send(user, text=WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT)
        if status in {WeeklyReportStatus.GREEN, WeeklyReportStatus.BLUE} and not draft.selected_step_ids:
            return self._send(user, text=_step_required_text(status))
        if not draft.report_text.strip():
            return self._send(user, text=WEEKLY_REPORT_EMPTY_TEXT)

        edit_report_id = _edit_report_id(draft.draft_id)
        if edit_report_id is not None:
            if not _editable_report_matches(
                self.sheets, edit_report_id, draft=draft,
                participant_id=participant_id, goal_id=goal_id,
            ):
                return self.recover_invalid_draft(user, reason="edit_scope_mismatch", now=now)
            self._update_existing_step_report(edit_report_id, draft=draft, submitted_at=submitted_at)
            self.drafts.clear_draft(user.telegram_id)
            return self._send(user, text="Отчёт по шагу обновлён.")

        return self._finalize_new_report(
            user, draft=draft, participant_id=participant_id, team_id=team_id,
            goal_id=goal_id, week_number=week_number, status=status,
            submitted_at=submitted_at,
        )

    def _finalize_new_report(
        self, user: TelegramUserContext, *, draft: WeeklyReportDraft,
        participant_id: str, team_id: str, goal_id: str, week_number: int,
        status: WeeklyReportStatus, submitted_at: str,
    ) -> FlowResponse:
        report_step_id = draft.selected_step_ids[0] if draft.selected_step_ids else None
        if report_step_id is not None and self.sheets.find_weekly_report_for_step_week(
            participant_id, step_id=report_step_id, week_number=week_number,
        ) is not None:
            self.drafts.clear_draft(user.telegram_id)
            return self._send(user, text="По этому шагу отчёт уже сохранён. Нажми «Редактировать отчёт».")
        if not self.drafts.claim_finalization(user.telegram_id, occurred_at=submitted_at):
            return self._send(user, text="Отчёт уже сохраняется. Подожди несколько секунд.")
        try:
            weekly_report_id = self._save_new_report(
                draft=draft, participant_id=participant_id, team_id=team_id,
                goal_id=goal_id, week_number=week_number, status=status,
                report_step_id=report_step_id, submitted_at=submitted_at,
            )
            self._apply_reported_step_status(
                draft=draft, participant_id=participant_id, goal_id=goal_id,
                week_number=week_number, weekly_report_id=weekly_report_id,
                status=status, submitted_at=submitted_at,
            )
            self._append_report_step_relations(
                draft=draft, participant_id=participant_id, goal_id=goal_id,
                week_number=week_number, status=status,
                weekly_report_id=weekly_report_id, submitted_at=submitted_at,
            )
        except Exception:
            self.drafts.release_finalization(user.telegram_id, occurred_at=submitted_at)
            raise
        self.drafts.clear_draft(user.telegram_id)
        return self._send(user, text=get_weekly_report_success_text(status))

    def _save_new_report(
        self, *, draft: WeeklyReportDraft, participant_id: str, team_id: str,
        goal_id: str, week_number: int, status: WeeklyReportStatus,
        report_step_id: str | None, submitted_at: str,
    ) -> str:
        weekly_report_id = _weekly_report_id(participant_id, week_number, report_step_id)
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
        return weekly_report_id

    def _append_report_step_relations(
        self, *, draft: WeeklyReportDraft, participant_id: str, goal_id: str,
        week_number: int, status: WeeklyReportStatus,
        weekly_report_id: str, submitted_at: str,
    ) -> None:
        if draft.selected_step_ids:
            relation_status = {
                WeeklyReportStatus.GREEN: "closed",
                WeeklyReportStatus.BLUE: "partial",
                WeeklyReportStatus.RED: "mentioned",
            }[status]
            for step_id in draft.selected_step_ids:
                relation = {
                    "weekly_report_step_id": _weekly_report_step_id(weekly_report_id, step_id),
                    "weekly_report_id": weekly_report_id,
                    "participant_id": participant_id,
                    "goal_id": goal_id,
                    "step_id": step_id,
                    "week_number": week_number,
                    "relation_status": relation_status,
                    "created_at": submitted_at,
                }
                if draft.metric_status:
                    relation["metric_status"] = draft.metric_status
                    relation["metric_result_text"] = draft.report_text
                self.sheets.append_weekly_report_step(relation)

    def _apply_reported_step_status(
        self, *, draft: WeeklyReportDraft, participant_id: str, goal_id: str,
        week_number: int, weekly_report_id: str, status: WeeklyReportStatus,
        submitted_at: str,
    ) -> None:
        if status is WeeklyReportStatus.GREEN:
            self.sheets.close_planned_steps(
                participant_id,
                goal_id,
                draft.selected_step_ids,
                closed_week_number=week_number,
                closed_report_id=weekly_report_id,
                closed_at=submitted_at,
            )
        elif status is WeeklyReportStatus.BLUE and draft.metric_status == "partial":
            self.sheets.mark_planned_steps_partial(
                participant_id, goal_id, draft.selected_step_ids, updated_at=submitted_at
            )

    def _update_existing_step_report(
        self, report_id: str, *, draft: WeeklyReportDraft, submitted_at: str
    ) -> None:
        self.sheets.update_weekly_report_text(
            report_id, report_text=draft.report_text,
            transcription_text=_voice_transcription_text(draft),
            audio_file_path=_voice_audio_file_path(draft), updated_at=submitted_at,
        )
        self.sheets.update_weekly_report_step_metric(
            report_id, metric_result_text=draft.report_text
        )

    def _resolve_context(
        self,
        user: TelegramUserContext,
        *,
        now: datetime,
    ) -> tuple[SheetRow, str, str, SheetRow, int] | FlowResponse:
        occurred_at = _occurred_at(now)
        self.drafts.purge_expired(occurred_at=occurred_at)
        participant = self.sheets.find_participant_by_telegram_id(user.telegram_id)
        if participant is None:
            return self._handle_unknown_user(user, occurred_at=occurred_at)

        if not _consent_is_given(participant):
            return self._send(user, text=CONSENT_TEXT, buttons=(CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON))
        if not _participant_can_report(participant, active_flow_id=self.active_flow_id):
            return self._send(user, text="Раздел недоступен для этого аккаунта.")

        if current_challenge_stage(now) in {"pre_start", "goal_setup", "steps_setup"}:
            return self._send(
                user,
                text=format_weekly_report_not_open_text(working_weeks_start_date()),
            )

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
            text="✅ Отчёт готов",
            callback_data=WEEKLY_REPORT_DONE_CALLBACK,
        ),
    )


def _metric_status_buttons() -> tuple[TelegramInlineButton, ...]:
    return (
        TelegramInlineButton("✅ Выполнена полностью", f"{WEEKLY_REPORT_METRIC_CALLBACK_PREFIX}completed"),
        TelegramInlineButton("🟦 Выполнена частично", f"{WEEKLY_REPORT_METRIC_CALLBACK_PREFIX}partial"),
        TelegramInlineButton("🟥 Не выполнена", f"{WEEKLY_REPORT_METRIC_CALLBACK_PREFIX}not_completed"),
    )


def _format_step_start_text(step: SheetRow) -> str:
    return "\n\n".join(
        (
            f"Шаг {_int_value(step.get('step_number'))}. {str(step.get('step_title') or '')}",
            f"Суть: {str(step.get('step_description') or 'не указана')}",
            f"Метрика: {str(step.get('step_metric') or 'не указана')}",
            "Как выполнена метрика этого шага?",
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


def _draft_has_duplicate_step_report(sheets: SheetsGateway, draft) -> bool:
    if _edit_report_id(draft.draft_id) is not None:
        return False
    if len(draft.selected_step_ids) != 1:
        return False
    return sheets.find_weekly_report_for_step_week(
        draft.participant_id, step_id=draft.selected_step_ids[0],
        week_number=draft.week_number,
    ) is not None


def _draft_scope_matches(
    draft: WeeklyReportDraft, *, participant_id: str, team_id: str,
    goal_id: str, week_number: int,
) -> bool:
    return (
        draft.participant_id == participant_id
        and draft.team_id == team_id
        and draft.goal_id == goal_id
        and draft.week_number == week_number
    )


def _participant_can_report(participant: SheetRow, *, active_flow_id: str | None) -> bool:
    return (
        str(participant.get("status", "")).strip().lower() == "active"
        and str(participant.get("role", "")).strip().lower() in {"participant", "captain"}
        and (
            active_flow_id is None
            or str(participant.get("flow_id", "")) == active_flow_id
        )
    )


def _editable_report_matches(
    sheets: SheetsGateway, report_id: str, *, draft: WeeklyReportDraft,
    participant_id: str, goal_id: str,
) -> bool:
    report = sheets.get_weekly_report(report_id)
    if report is None or len(draft.selected_step_ids) != 1:
        return False
    if (
        str(report.get("participant_id") or "") != participant_id
        or str(report.get("goal_id") or "") != goal_id
    ):
        return False
    return any(
        str(row.get("weekly_report_id") or "") == report_id
        and str(row.get("participant_id") or "") == participant_id
        and str(row.get("step_id") or "") == draft.selected_step_ids[0]
        for row in sheets.list_weekly_report_steps()
    )


def _draft_id(participant_id: str, week_number: int, *, step_id: str | None = None) -> str:
    suffix = f":step-{step_id}" if step_id else ""
    return f"weekly-report:{participant_id}:week-{week_number:02d}{suffix}"


def _edit_draft_id(weekly_report_id: str) -> str:
    return f"weekly-report-edit:{weekly_report_id}"


def _edit_report_id(draft_id: str) -> str | None:
    prefix = "weekly-report-edit:"
    if draft_id.startswith(prefix):
        return draft_id[len(prefix):]
    return None


def _weekly_report_id(participant_id: str, week_number: int, step_id: str | None = None) -> str:
    suffix = f":step-{step_id}" if step_id else ""
    return f"WR:{participant_id}:week-{week_number:02d}{suffix}"


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
