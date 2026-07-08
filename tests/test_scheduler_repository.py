import sqlite3
from pathlib import Path

from app.storage.scheduler import SchedulerJobRepository
from app.storage.sqlite import initialize_schema


def test_start_and_finish_job_run_records_status(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = SchedulerJobRepository(db_path)

    run_id = repository.start_job_run(
        job_type="week_close",
        week_number=4,
        scheduled_for="2026-07-05T23:59:00+05:00",
        idempotency_key="week_close:week_04",
        started_at="2026-07-05T23:59:00+05:00",
    )
    repository.finish_job_run(
        run_id,
        status="completed",
        finished_at="2026-07-05T23:59:05+05:00",
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT runs.job_type, runs.week_number, runs.status, runs.finished_at, jobs.status
            FROM job_runs AS runs
            JOIN scheduler_jobs AS jobs ON jobs.job_id = runs.job_id
            WHERE runs.job_run_id = ?
            """,
            (run_id,),
        ).fetchone()

    assert row == (
        "week_close",
        4,
        "completed",
        "2026-07-05T23:59:05+05:00",
        "completed",
    )


def test_duplicate_idempotency_key_is_not_reinserted(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = SchedulerJobRepository(db_path)

    first_run_id = repository.start_job_run(
        job_type="week_close",
        week_number=4,
        scheduled_for="2026-07-05T23:59:00+05:00",
        idempotency_key="week_close:week_04",
        started_at="2026-07-05T23:59:00+05:00",
    )
    second_run_id = repository.start_job_run(
        job_type="week_close",
        week_number=4,
        scheduled_for="2026-07-05T23:59:00+05:00",
        idempotency_key="week_close:week_04",
        started_at="2026-07-05T23:59:01+05:00",
    )

    with sqlite3.connect(db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0]
        job_count = connection.execute("SELECT COUNT(*) FROM scheduler_jobs").fetchone()[0]

    assert second_run_id == first_run_id
    assert run_count == 1
    assert job_count == 1


def test_reminder_attempt_upserts_retry_state(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = SchedulerJobRepository(db_path)

    repository.record_reminder_attempt(
        participant_id="P001",
        team_id="T001",
        week_number=4,
        reminder_type="sunday_2300",
        sent_at="2026-07-05T23:00:00+05:00",
        status="failed",
        error_message="telegram unavailable",
    )
    repository.record_reminder_attempt(
        participant_id="P001",
        team_id="T001",
        week_number=4,
        reminder_type="sunday_2300",
        sent_at="2026-07-05T23:00:02+05:00",
        status="sent",
        telegram_message_id=501,
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT status, telegram_message_id, error_message, attempt_count, sent_at
            FROM reminder_log
            WHERE participant_id = 'P001'
            """
        ).fetchone()

    assert row == ("sent", 501, None, 2, "2026-07-05T23:00:02+05:00")


def test_successful_reminder_lookup_prevents_duplicate_send(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = SchedulerJobRepository(db_path)

    assert not repository.has_successful_reminder("P001", week_number=4, reminder_type="sunday_2300")

    repository.record_reminder_attempt(
        participant_id="P001",
        team_id="T001",
        week_number=4,
        reminder_type="sunday_2300",
        sent_at="2026-07-05T23:00:00+05:00",
        status="sent",
    )

    assert repository.has_successful_reminder("P001", week_number=4, reminder_type="sunday_2300")


def test_record_error_stores_safe_technical_context(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = SchedulerJobRepository(db_path)

    repository.record_error(
        module="scheduler",
        error_type="missing_tracker_chat_id",
        severity="medium",
        message="tracker_id=TR001 has no telegram_id",
        created_at="2026-07-05T23:59:00+05:00",
        participant_id="P001",
        team_id="T001",
        admin_notified=True,
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT module, error_type, severity, participant_id, team_id, message, admin_notified
            FROM error_events
            """
        ).fetchone()

    assert row == (
        "scheduler",
        "missing_tracker_chat_id",
        "medium",
        "P001",
        "T001",
        "tracker_id=TR001 has no telegram_id",
        1,
    )
