"""Challenge calendar and scheduler constants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "Asia/Yekaterinburg"
DEFAULT_CHALLENGE_START_DATE = date(2026, 5, 25)
SETUP_WEEK_COUNT = 2
WORKING_WEEK_COUNT = 8
CHALLENGE_TOTAL_WEEKS = WORKING_WEEK_COUNT
CHALLENGE_TOTAL_CALENDAR_WEEKS = SETUP_WEEK_COUNT + WORKING_WEEK_COUNT
FINAL_SUMMARY_WINDOW_DAYS = 4
_challenge_start_date = DEFAULT_CHALLENGE_START_DATE


@dataclass(frozen=True)
class ScheduleItem:
    job_type: str
    weekday: int
    run_at: time
    description: str


def configure_challenge_calendar(*, start_date: date) -> None:
    """Configure the shared challenge start date for the running process."""

    global _challenge_start_date
    _challenge_start_date = start_date


def challenge_start_date() -> date:
    """Return the first setup-week date from the active challenge flow."""

    return _challenge_start_date


def working_weeks_start_date() -> date:
    return challenge_start_date() + timedelta(weeks=SETUP_WEEK_COUNT)


def challenge_end_date() -> date:
    return challenge_start_date() + timedelta(weeks=CHALLENGE_TOTAL_CALENDAR_WEEKS) - timedelta(days=1)


def final_summary_end_date() -> date:
    return challenge_end_date() + timedelta(days=FINAL_SUMMARY_WINDOW_DAYS)


def current_challenge_week_number(now: datetime) -> int:
    local_now = _as_yekaterinburg(now)
    days_since_working_start = (local_now.date() - working_weeks_start_date()).days
    return max(1, min(WORKING_WEEK_COUNT, days_since_working_start // 7 + 1))


def current_challenge_stage(now: datetime) -> str:
    local_now = _as_yekaterinburg(now)
    current_date = local_now.date()
    if current_date < challenge_start_date():
        return "pre_start"

    days_since_start = (current_date - challenge_start_date()).days
    if days_since_start < 7:
        return "goal_setup"
    if days_since_start < 14:
        return "steps_setup"

    working_week_number = days_since_start // 7 - SETUP_WEEK_COUNT + 1
    if 1 <= working_week_number <= WORKING_WEEK_COUNT:
        return f"week_{working_week_number:02d}"
    if current_date <= final_summary_end_date():
        return "final_summary"
    return "completed"


def is_working_week(now: datetime) -> bool:
    return current_challenge_stage(now).startswith("week_")


def challenge_week_date_range(now: datetime) -> tuple[date, date]:
    local_now = _as_yekaterinburg(now)
    start = local_now.date() - timedelta(days=local_now.weekday())
    return start, start + timedelta(days=6)


def weekly_report_deadline(now: datetime) -> datetime:
    local_now = _as_yekaterinburg(now)
    days_until_sunday = 6 - local_now.weekday()
    deadline_date = local_now.date() + timedelta(days=days_until_sunday)
    return datetime.combine(deadline_date, time(23, 59), tzinfo=ZoneInfo(TIMEZONE_NAME))


def is_weekly_report_open(now: datetime) -> bool:
    local_now = _as_yekaterinburg(now)
    return is_working_week(local_now) and local_now <= weekly_report_deadline(local_now)


def reminder_schedule() -> tuple[ScheduleItem, ...]:
    return (
        ScheduleItem("monday_reminder", 0, time(10, 0), "start-of-week reminder"),
        ScheduleItem("monday_focus_1300", 0, time(13, 0), "missing weekly focus reminder"),
        ScheduleItem("monday_focus_1900", 0, time(19, 0), "last missing weekly focus reminder"),
        ScheduleItem(
            "weekly_focus_summary_captain",
            0,
            time(21, 0),
            "captain weekly focus summary",
        ),
        ScheduleItem("wednesday_checkin", 2, time(10, 0), "soft check-in"),
        ScheduleItem("sunday_1800_checkin", 6, time(18, 0), "final check-in"),
        ScheduleItem("sunday_2230_reminder", 6, time(22, 30), "missing-report reminder"),
        ScheduleItem("sunday_2300_reminder", 6, time(23, 0), "last missing-report reminder"),
        ScheduleItem("week_close", 6, time(23, 59), "hard weekly report deadline"),
    )


def build_idempotency_key(
    job_type: str,
    *,
    week_number: int | None = None,
    participant_id: str | None = None,
    recipient_id: str | None = None,
) -> str:
    parts = [job_type]
    if week_number is not None:
        parts.append(f"week_{week_number:02d}")
    if participant_id is not None:
        parts.append(f"participant_{participant_id}")
    if recipient_id is not None:
        parts.append(f"recipient_{recipient_id}")
    return ":".join(parts)


def _as_yekaterinburg(value: datetime) -> datetime:
    timezone = ZoneInfo(TIMEZONE_NAME)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)
