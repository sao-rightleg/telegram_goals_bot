"""Executable challenge calendar and scheduler constants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


TIMEZONE_NAME = "Asia/Yekaterinburg"
CHALLENGE_END_DATE = date(2026, 7, 31)
CHALLENGE_TOTAL_WEEKS = 8
SETUP_WEEK_COUNT = 2
EXECUTION_WEEK_COUNT = 6
FINAL_SUMMARY_WINDOW_DAYS = 4


@dataclass(frozen=True)
class ScheduleItem:
    job_type: str
    weekday: int
    run_at: time
    description: str


def challenge_start_date() -> date:
    """Return the first date of week 1 from the approved shared calendar."""

    return CHALLENGE_END_DATE - timedelta(weeks=CHALLENGE_TOTAL_WEEKS) + timedelta(days=1)


def final_summary_end_date() -> date:
    return CHALLENGE_END_DATE + timedelta(days=FINAL_SUMMARY_WINDOW_DAYS)


def current_challenge_week_number(now: datetime) -> int:
    local_now = _as_yekaterinburg(now)
    days_since_start = (local_now.date() - challenge_start_date()).days
    return max(1, min(CHALLENGE_TOTAL_WEEKS, days_since_start // 7 + 1))


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
    return local_now <= weekly_report_deadline(local_now)


def reminder_schedule() -> tuple[ScheduleItem, ...]:
    return (
        ScheduleItem("monday_reminder", 0, time(10, 0), "start-of-week reminder"),
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
