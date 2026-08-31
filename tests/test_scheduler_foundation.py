from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.scheduler.calendar import (
    CHALLENGE_TOTAL_CALENDAR_WEEKS,
    CHALLENGE_TOTAL_WEEKS,
    DEFAULT_CHALLENGE_START_DATE,
    FINAL_SUMMARY_WINDOW_DAYS,
    SETUP_WEEK_COUNT,
    TIMEZONE_NAME,
    build_idempotency_key,
    challenge_end_date,
    challenge_start_date,
    current_challenge_stage,
    final_summary_end_date,
    working_weeks_start_date,
    reminder_schedule,
)


YEKT = ZoneInfo(TIMEZONE_NAME)


def test_timezone_is_yekaterinburg() -> None:
    assert TIMEZONE_NAME == "Asia/Yekaterinburg"


def test_timezone_is_not_overridden_by_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_TIMEZONE", "Europe/Berlin")

    assert TIMEZONE_NAME == "Asia/Yekaterinburg"


def test_default_challenge_start_date_is_stable() -> None:
    assert DEFAULT_CHALLENGE_START_DATE == date(2026, 5, 25)


def test_final_summary_window_is_four_days() -> None:
    assert CHALLENGE_TOTAL_WEEKS == 8
    assert SETUP_WEEK_COUNT == 2
    assert CHALLENGE_TOTAL_CALENDAR_WEEKS == 10
    assert FINAL_SUMMARY_WINDOW_DAYS == 4
    assert challenge_start_date() == DEFAULT_CHALLENGE_START_DATE
    assert working_weeks_start_date() == date(2026, 6, 8)
    assert challenge_end_date() == date(2026, 8, 2)
    assert final_summary_end_date() == challenge_end_date() + timedelta(days=4)


def test_challenge_stage_names_setup_and_working_weeks() -> None:
    assert current_challenge_stage(datetime(2026, 5, 24, 10, tzinfo=YEKT)) == "pre_start"
    assert current_challenge_stage(datetime(2026, 5, 25, 10, tzinfo=YEKT)) == "goal_setup"
    assert current_challenge_stage(datetime(2026, 6, 1, 10, tzinfo=YEKT)) == "steps_setup"
    assert current_challenge_stage(datetime(2026, 6, 8, 10, tzinfo=YEKT)) == "week_01"
    assert current_challenge_stage(datetime(2026, 7, 27, 10, tzinfo=YEKT)) == "week_08"
    assert current_challenge_stage(datetime(2026, 8, 3, 10, tzinfo=YEKT)) == "final_summary"
    assert current_challenge_stage(datetime(2026, 8, 7, 10, tzinfo=YEKT)) == "completed"


def test_reminder_schedule_matches_product_decisions() -> None:
    schedule = {item.job_type: item for item in reminder_schedule()}

    assert schedule["monday_reminder"].weekday == 0
    assert schedule["monday_reminder"].run_at == time(10, 0)
    assert schedule["monday_focus_1300"].weekday == 0
    assert schedule["monday_focus_1300"].run_at == time(13, 0)
    assert schedule["monday_focus_1900"].weekday == 0
    assert schedule["monday_focus_1900"].run_at == time(19, 0)
    assert schedule["weekly_focus_summary_captain"].weekday == 0
    assert schedule["weekly_focus_summary_captain"].run_at == time(21, 0)
    assert schedule["wednesday_checkin"].weekday == 2
    assert schedule["wednesday_checkin"].run_at == time(10, 0)
    assert schedule["sunday_1800_checkin"].weekday == 6
    assert schedule["sunday_1800_checkin"].run_at == time(18, 0)
    assert schedule["sunday_2230_reminder"].run_at == time(22, 30)
    assert schedule["sunday_2300_reminder"].run_at == time(23, 0)
    assert schedule["week_close"].run_at == time(23, 59)


def test_scheduler_idempotency_keys_are_stable() -> None:
    assert build_idempotency_key("week_close", week_number=3) == "week_close:week_03"
    assert (
        build_idempotency_key("report_send", week_number=3, recipient_id="P001")
        == "report_send:week_03:recipient_P001"
    )
