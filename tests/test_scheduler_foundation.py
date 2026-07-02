from datetime import date, time, timedelta

from app.scheduler.calendar import (
    CHALLENGE_END_DATE,
    CHALLENGE_TOTAL_WEEKS,
    EXECUTION_WEEK_COUNT,
    FINAL_SUMMARY_WINDOW_DAYS,
    SETUP_WEEK_COUNT,
    TIMEZONE_NAME,
    build_idempotency_key,
    challenge_start_date,
    final_summary_end_date,
    reminder_schedule,
)


def test_timezone_is_yekaterinburg() -> None:
    assert TIMEZONE_NAME == "Asia/Yekaterinburg"


def test_timezone_is_not_overridden_by_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_TIMEZONE", "Europe/Berlin")

    assert TIMEZONE_NAME == "Asia/Yekaterinburg"


def test_challenge_end_date_is_fixed() -> None:
    assert CHALLENGE_END_DATE == date(2026, 7, 31)


def test_final_summary_window_is_four_days() -> None:
    assert CHALLENGE_TOTAL_WEEKS == 8
    assert SETUP_WEEK_COUNT == 2
    assert EXECUTION_WEEK_COUNT == 6
    assert FINAL_SUMMARY_WINDOW_DAYS == 4
    assert final_summary_end_date() == CHALLENGE_END_DATE + timedelta(days=4)
    assert challenge_start_date() == CHALLENGE_END_DATE - timedelta(weeks=8) + timedelta(days=1)


def test_reminder_schedule_matches_product_decisions() -> None:
    schedule = {item.job_type: item for item in reminder_schedule()}

    assert schedule["monday_reminder"].weekday == 0
    assert schedule["monday_reminder"].run_at == time(10, 0)
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
