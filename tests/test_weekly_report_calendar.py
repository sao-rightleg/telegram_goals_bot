from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduler.calendar import (
    TIMEZONE_NAME,
    closed_challenge_week_count,
    current_challenge_week_number,
    is_weekly_report_open,
    weekly_report_deadline,
)


YEKT = ZoneInfo(TIMEZONE_NAME)
UTC = ZoneInfo("UTC")


def test_current_week_uses_challenge_start_and_yekaterinburg_timezone() -> None:
    now = datetime(2026, 7, 2, 4, 0, tzinfo=UTC)

    assert current_challenge_week_number(now) == 4


def test_deadline_is_sunday_2359_yekaterinburg() -> None:
    now = datetime(2026, 7, 2, 10, 0, tzinfo=YEKT)

    deadline = weekly_report_deadline(now)

    assert deadline == datetime(2026, 7, 5, 23, 59, tzinfo=YEKT)
    assert deadline.weekday() == 6


def test_closed_week_count_distinguishes_past_from_current_and_future() -> None:
    assert closed_challenge_week_count(datetime(2026, 6, 14, 23, 58, tzinfo=YEKT)) == 0
    assert closed_challenge_week_count(datetime(2026, 6, 14, 23, 59, tzinfo=YEKT)) == 0
    assert closed_challenge_week_count(datetime(2026, 6, 14, 23, 59, 1, tzinfo=YEKT)) == 1
    assert closed_challenge_week_count(datetime(2026, 7, 2, 10, 0, tzinfo=YEKT)) == 3


def test_report_allowed_before_or_at_deadline() -> None:
    assert is_weekly_report_open(datetime(2026, 7, 5, 23, 58, tzinfo=YEKT)) is True
    assert is_weekly_report_open(datetime(2026, 7, 5, 23, 59, tzinfo=YEKT)) is True


def test_report_rejected_after_deadline() -> None:
    assert is_weekly_report_open(datetime(2026, 7, 5, 23, 59, 1, tzinfo=YEKT)) is False


def test_helpers_are_deterministic_with_explicit_now() -> None:
    first = datetime(2026, 7, 2, 10, 0, tzinfo=YEKT)
    second = datetime(2026, 7, 2, 10, 0, tzinfo=YEKT)

    assert current_challenge_week_number(first) == current_challenge_week_number(second)
    assert weekly_report_deadline(first) == weekly_report_deadline(second)
    assert is_weekly_report_open(first) == is_weekly_report_open(second)
