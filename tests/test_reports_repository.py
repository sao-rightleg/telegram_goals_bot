import sqlite3
from pathlib import Path

from app.storage.reports import ReportStateRepository
from app.storage.sqlite import initialize_schema


def test_report_job_run_records_lifecycle_status(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)

    run_id = repository.start_job_run(
        week_number=5,
        idempotency_key="reports:week_05",
        started_at="2026-07-12T23:59:00+05:00",
    )
    repository.finish_job_run(
        run_id,
        status="completed",
        finished_at="2026-07-12T23:59:10+05:00",
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT week_number, job_type, idempotency_key, status, finished_at, error_message
            FROM report_job_runs
            WHERE report_job_run_id = ?
            """,
            (run_id,),
        ).fetchone()

    assert row == (
        5,
        "report_generate_send",
        "reports:week_05",
        "completed",
        "2026-07-12T23:59:10+05:00",
        None,
    )


def test_report_job_run_idempotency_key_is_unique(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)

    first_run_id = repository.start_job_run(
        week_number=5,
        idempotency_key="reports:week_05",
        started_at="2026-07-12T23:59:00+05:00",
    )
    second_run_id = repository.start_job_run(
        week_number=5,
        idempotency_key="reports:week_05",
        started_at="2026-07-12T23:59:01+05:00",
    )

    with sqlite3.connect(db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM report_job_runs").fetchone()[0]

    assert second_run_id == first_run_id
    assert run_count == 1


def test_delivery_log_prevents_duplicate_successful_send(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)

    assert not repository.has_successful_delivery(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
    )

    repository.record_delivery_attempt(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
        chat_id="1001",
        status="sent",
        sent_at="2026-07-12T23:59:03+05:00",
        telegram_message_id=501,
    )

    assert repository.has_successful_delivery(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
    )


def test_delivery_log_records_failure_and_attempt_count(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)

    repository.record_delivery_attempt(
        week_number=5,
        report_type="pdf_team_report",
        scope_id="T001",
        recipient_type="tracker",
        recipient_id="TR001",
        chat_id="3001",
        status="failed",
        sent_at="2026-07-12T23:59:03+05:00",
        file_path="/tmp/team.pdf",
        error_message="telegram token=secret raw participant text",
    )
    repository.record_delivery_attempt(
        week_number=5,
        report_type="pdf_team_report",
        scope_id="T001",
        recipient_type="tracker",
        recipient_id="TR001",
        chat_id="3001",
        status="sent",
        sent_at="2026-07-12T23:59:10+05:00",
        file_path="/tmp/team.pdf",
        telegram_message_id=502,
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT status, telegram_message_id, file_path, error_message, attempt_count
            FROM report_delivery_log
            WHERE recipient_id = 'TR001'
            """
        ).fetchone()

    assert row == ("sent", 502, "/tmp/team.pdf", None, 2)


def test_delivery_error_message_is_sanitized(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)

    repository.record_delivery_attempt(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
        chat_id="1001",
        status="failed",
        sent_at="2026-07-12T23:59:03+05:00",
        error_message="token=abc123\nparticipant report body",
    )

    with sqlite3.connect(db_path) as connection:
        message = connection.execute(
            "SELECT error_message FROM report_delivery_log"
        ).fetchone()[0]

    assert "token=" not in message
    assert "\n" not in message
    assert len(message) <= 240
