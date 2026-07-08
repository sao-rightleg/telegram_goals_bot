"""Scheduler job service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.bot.messages import format_scheduler_reminder_text, format_silent_participants_notification
from app.scheduler.calendar import build_idempotency_key, current_challenge_week_number
from app.services.notifications import NotificationCategory, NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import SheetsGateway
from app.storage.scheduler import SchedulerJobRepository


@dataclass(frozen=True)
class ReminderJobResult:
    sent_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True)
class WeekCloseResult:
    gray_created_count: int = 0
    existing_count: int = 0
    failed_count: int = 0
    notified_team_count: int = 0


@dataclass(frozen=True)
class SilentParticipant:
    participant_id: str
    team_id: str
    full_name: str


@dataclass(frozen=True)
class SchedulerService:
    sheets: SheetsGateway
    notification_router: NotificationRouter
    repository: SchedulerJobRepository
    max_reminder_attempts: int = 3

    def run_reminder(self, reminder_type: str, *, now: datetime) -> ReminderJobResult:
        week_number = current_challenge_week_number(now)
        sent_count = 0
        skipped_count = 0
        failed_count = 0
        text = format_scheduler_reminder_text(reminder_type)
        scheduled_for = now.isoformat()
        job_run_id = self.repository.start_job_run(
            job_type=reminder_type,
            week_number=week_number,
            scheduled_for=scheduled_for,
            idempotency_key=build_idempotency_key(reminder_type, week_number=week_number),
            started_at=scheduled_for,
        )
        reminder_log_type = _reminder_log_type(reminder_type)

        for participant in self.sheets.list_participants():
            participant_id = _string_value(participant.get("participant_id"))
            team_id = _string_value(participant.get("team_id"))
            if not self._is_reminder_eligible(participant, week_number=week_number):
                skipped_count += 1
                continue

            if self.repository.has_successful_reminder(
                participant_id,
                week_number=week_number,
                reminder_type=reminder_log_type,
            ):
                skipped_count += 1
                continue

            chat_id = _chat_id(participant)
            if chat_id is None:
                skipped_count += 1
                self._notify_admin_error(
                    "reminder_missing_chat_id",
                    f"reminder_missing_chat_id participant_id={participant_id}",
                    participant_id=participant_id,
                    team_id=team_id,
                    now=now,
                )
                continue

            if self._send_reminder_with_retry(
                chat_id=chat_id,
                text=text,
                participant_id=participant_id,
                team_id=team_id,
                week_number=week_number,
                reminder_type=reminder_log_type,
                now=now,
            ):
                sent_count += 1
            else:
                failed_count += 1

        status = "failed" if failed_count else "completed"
        self.repository.finish_job_run(
            job_run_id,
            status=status,
            finished_at=now.isoformat(),
            error_message=None if not failed_count else f"failed_count={failed_count}",
        )
        return ReminderJobResult(
            sent_count=sent_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
        )

    def close_week(self, *, now: datetime) -> WeekCloseResult:
        week_number = current_challenge_week_number(now)
        gray_created_count = 0
        existing_count = 0
        failed_count = 0
        silent_by_team: dict[str, list[SilentParticipant]] = {}
        job_run_id = self.repository.start_job_run(
            job_type="week_close",
            week_number=week_number,
            scheduled_for=now.isoformat(),
            idempotency_key=build_idempotency_key("week_close", week_number=week_number),
            started_at=now.isoformat(),
        )

        for participant in self.sheets.list_participants():
            if _normalized_string(participant.get("status")) == "dropped":
                continue

            participant_id = _string_value(participant.get("participant_id"))
            team_id = _string_value(participant.get("team_id"))
            if not participant_id:
                failed_count += 1
                self._notify_admin_error(
                    "week_close_missing_participant_id",
                    "week_close_missing_participant_id",
                    participant_id="",
                    team_id=team_id,
                    now=now,
                )
                continue

            if self.sheets.find_weekly_report(participant_id, week_number=week_number) is not None:
                existing_count += 1
                continue

            try:
                self.sheets.append_weekly_report(
                    _gray_weekly_report_row(
                        participant,
                        goal_id=_active_goal_id(self.sheets, participant_id),
                        week_number=week_number,
                        submitted_at=now.isoformat(),
                    )
                )
                gray_created_count += 1
                if _normalized_string(participant.get("role")) in ("", "participant"):
                    silent_by_team.setdefault(team_id, []).append(
                        SilentParticipant(
                            participant_id=participant_id,
                            team_id=team_id,
                            full_name=_display_name(participant),
                        )
                    )
            except Exception as exc:  # pragma: no cover - concrete exception type belongs to Sheets adapter
                failed_count += 1
                self._notify_admin_error(
                    "week_close_gray_failed",
                    f"week_close_gray_failed participant_id={participant_id}",
                    participant_id=participant_id,
                    team_id=team_id,
                    now=now,
                )

        notified_team_count = self._send_silent_notifications(
            silent_by_team,
            week_number=week_number,
            now=now,
        )
        status = "failed" if failed_count else "completed"
        self.repository.finish_job_run(
            job_run_id,
            status=status,
            finished_at=now.isoformat(),
            error_message=None if not failed_count else f"failed_count={failed_count}",
        )
        return WeekCloseResult(
            gray_created_count=gray_created_count,
            existing_count=existing_count,
            failed_count=failed_count,
            notified_team_count=notified_team_count,
        )

    def _is_reminder_eligible(self, participant: dict[str, object], *, week_number: int) -> bool:
        if _normalized_string(participant.get("status")) == "dropped":
            return False
        if not _consent_is_given(participant):
            return False

        participant_id = _string_value(participant.get("participant_id"))
        if not participant_id:
            return False
        return self.sheets.find_weekly_report(participant_id, week_number=week_number) is None

    def _send_reminder_with_retry(
        self,
        *,
        chat_id: str,
        text: str,
        participant_id: str,
        team_id: str,
        week_number: int,
        reminder_type: str,
        now: datetime,
    ) -> bool:
        for _attempt in range(self.max_reminder_attempts):
            try:
                messages = self.notification_router.send(
                    category=NotificationCategory.PARTICIPANT_MESSAGE,
                    text=text,
                    recipients=(Recipient(RecipientType.PARTICIPANT, chat_id),),
                )
                telegram_message_id = _telegram_message_id(messages[0]) if messages else None
                self.repository.record_reminder_attempt(
                    participant_id=participant_id,
                    team_id=team_id,
                    week_number=week_number,
                    reminder_type=reminder_type,
                    sent_at=now.isoformat(),
                    status="sent",
                    telegram_message_id=telegram_message_id,
                )
                return True
            except Exception as exc:  # pragma: no cover - concrete exception type belongs to bot adapter
                self.repository.record_reminder_attempt(
                    participant_id=participant_id,
                    team_id=team_id,
                    week_number=week_number,
                    reminder_type=reminder_type,
                    sent_at=now.isoformat(),
                    status="failed",
                    error_message=type(exc).__name__,
                )

        self._notify_admin_error(
            "reminder_send_failed",
            f"reminder_send_failed participant_id={participant_id}",
            participant_id=participant_id,
            team_id=team_id,
            now=now,
        )
        return False

    def _notify_admin_error(
        self,
        error_type: str,
        message: str,
        *,
        participant_id: str,
        team_id: str,
        now: datetime,
    ) -> None:
        self.repository.record_error(
            module="scheduler",
            error_type=error_type,
            severity="medium",
            message=message,
            created_at=now.isoformat(),
            participant_id=participant_id,
            team_id=team_id,
            admin_notified=True,
        )
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=message,
            recipients=(),
        )

    def _send_silent_notifications(
        self,
        silent_by_team: dict[str, list[SilentParticipant]],
        *,
        week_number: int,
        now: datetime,
    ) -> int:
        notified_team_count = 0
        teams = {str(row.get("team_id")): row for row in self.sheets.list_teams()}
        for team_id, participants in silent_by_team.items():
            if not participants:
                continue
            team = teams.get(team_id)
            if team is None:
                continue

            text = format_silent_participants_notification(
                week_number=week_number,
                participants=participants,
            )
            sent_for_team = False
            for recipient_row, recipient_type, error_label in self._team_silent_recipients(team):
                chat_id = _chat_id(recipient_row)
                if chat_id is None:
                    self._notify_admin_error(
                        "silent_notification_missing_recipient",
                        (
                            "silent_notification_missing_recipient "
                            f"team_id={team_id} recipient_type={recipient_type.value}"
                        ),
                        participant_id="",
                        team_id=team_id,
                        now=now,
                    )
                    continue

                try:
                    self.notification_router.send(
                        category=NotificationCategory.OPERATIONAL_NOTIFICATION,
                        text=text,
                        recipients=(Recipient(recipient_type, chat_id),),
                    )
                    sent_for_team = True
                except Exception as exc:  # pragma: no cover - concrete exception type belongs to bot adapter
                    self._notify_admin_error(
                        error_label,
                        f"{error_label} team_id={team_id}",
                        participant_id="",
                        team_id=team_id,
                        now=now,
                    )
            if sent_for_team:
                notified_team_count += 1
        return notified_team_count

    def _team_silent_recipients(
        self,
        team: dict[str, object],
    ) -> tuple[tuple[dict[str, object], RecipientType, str], ...]:
        recipients: list[tuple[dict[str, object], RecipientType, str]] = []
        captain_id = _string_value(team.get("captain_id"))
        if captain_id:
            captain = self.sheets.get_participant(captain_id)
            if captain is not None:
                recipients.append((captain, RecipientType.CAPTAIN, "silent_notification_send_failed"))
            else:
                recipients.append(({}, RecipientType.CAPTAIN, "silent_notification_send_failed"))

        tracker_id = _string_value(team.get("tracker_id"))
        if tracker_id:
            tracker = self.sheets.get_tracker(tracker_id)
            if tracker is not None:
                recipients.append((tracker, RecipientType.TRACKER, "silent_notification_send_failed"))
            else:
                recipients.append(({}, RecipientType.TRACKER, "silent_notification_send_failed"))
        return tuple(recipients)


def _reminder_log_type(reminder_type: str) -> str:
    return {
        "monday_reminder": "monday_start",
        "wednesday_checkin": "wednesday_checkin",
        "sunday_1800_checkin": "sunday_1800",
        "sunday_2230_reminder": "sunday_2230",
        "sunday_2300_reminder": "sunday_2300",
    }[reminder_type]


def _chat_id(participant: dict[str, object]) -> str | None:
    raw = participant.get("chat_id") or participant.get("telegram_id")
    if raw in (None, ""):
        return None
    return str(raw)


def _consent_is_given(participant: dict[str, object]) -> bool:
    return participant.get("consent_given") is True


def _string_value(value: object) -> str:
    return "" if value is None else str(value)


def _normalized_string(value: object) -> str:
    return _string_value(value).strip().lower()


def _telegram_message_id(message: object) -> int | None:
    value = getattr(message, "telegram_message_id", None)
    return value if isinstance(value, int) else None


def _display_name(participant: dict[str, object]) -> str:
    name = participant.get("full_name") or participant.get("display_name") or participant.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Участник без имени"


def _active_goal_id(sheets: SheetsGateway, participant_id: str) -> str:
    goal = sheets.get_active_goal(participant_id)
    if goal is None:
        return ""
    return _string_value(goal.get("goal_id"))


def _gray_weekly_report_row(
    participant: dict[str, object],
    *,
    goal_id: str,
    week_number: int,
    submitted_at: str,
) -> dict[str, object]:
    participant_id = _string_value(participant.get("participant_id"))
    return {
        "weekly_report_id": f"WR:{participant_id}:week-{week_number:02d}",
        "participant_id": participant_id,
        "team_id": _string_value(participant.get("team_id")),
        "goal_id": goal_id,
        "week_number": week_number,
        "status_code": "gray",
        "status_symbol": "⬜",
        "score": 0,
        "status_score": 0,
        "report_text": "",
        "transcription_text": "",
        "audio_file_path": "",
        "audio_deleted_at": "",
        "submitted_at": submitted_at,
        "submitted_by_id": "system",
        "submitted_by_role": "system",
        "flow_source": "system_deadline",
        "submitted_source": "system_deadline",
    }
