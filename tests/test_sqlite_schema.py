import sqlite3
from pathlib import Path

import pytest

from app.storage.sqlite import (
    BUSINESS_PRIMARY_TABLES,
    REQUIRED_TECHNICAL_TABLES,
    initialize_schema,
    list_indexes,
    list_tables,
)


def test_init_creates_required_technical_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)

    assert REQUIRED_TECHNICAL_TABLES <= list_tables(db_path)


def test_init_does_not_create_business_primary_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_init_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)
    initialize_schema(db_path)

    assert REQUIRED_TECHNICAL_TABLES <= list_tables(db_path)


def test_draft_sessions_owns_draft_id(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO draft_sessions (
                draft_id, draft_type, participant_id, telegram_id, flow_source, status,
                created_at, updated_at
            )
            VALUES (
                'draft-1', 'weekly_report', 'P001', 12345, 'participant_bot', 'active',
                '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO draft_messages (
                draft_id, participant_id, telegram_id, message_order, message_type, text,
                created_at
            )
            VALUES (
                'draft-1', 'P001', 12345, 1, 'text', 'draft text',
                '2026-07-01T10:00:01+05:00'
            )
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO draft_messages (
                    draft_id, participant_id, telegram_id, message_order, message_type, text,
                    created_at
                )
                VALUES (
                    'missing-draft', 'P001', 12345, 1, 'text', 'orphan text',
                    '2026-07-01T10:00:02+05:00'
                )
                """
            )


def test_captain_manual_report_values_are_allowed(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO draft_sessions (
                draft_id, draft_type, participant_id, telegram_id, flow_source, status,
                created_at, updated_at
            )
            VALUES (
                'captain-draft-1', 'captain_manual_report', 'P001', 2001,
                'captain_manual', 'active',
                '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO draft_reports (
                draft_id, participant_id, team_id, goal_id, week_number, flow_source,
                status_code, status_symbol, submitted_by_id, submitted_by_role,
                created_at, updated_at
            )
            VALUES (
                'captain-draft-1', 'P001', 'T001', 'G001', 4, 'captain_manual',
                'gray', '⬜', 'C001', 'captain',
                '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dialog_states (
                telegram_id, participant_id, role, flow, step, week_number,
                selected_participant_id, draft_id, started_at, updated_at
            )
            VALUES (
                2001, 'C001', 'captain', 'captain_manual_report', 'draft_started', 4,
                'P001', 'captain-draft-1',
                '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
            )
            """
        )

        row = connection.execute(
            """
            SELECT dialog_states.flow, dialog_states.selected_participant_id, draft_reports.submitted_by_role
            FROM dialog_states
            JOIN draft_reports ON draft_reports.draft_id = dialog_states.draft_id
            """
        ).fetchone()

    assert row == ("captain_manual_report", "P001", "captain")


def test_scheduler_and_reminders_have_idempotency_constraints(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO scheduler_jobs (
                job_id, job_type, week_number, scheduled_for, timezone, status,
                created_at, updated_at
            )
            VALUES (
                'job-1', 'week_close', 3, '2026-07-05T23:59:00+05:00',
                'Asia/Yekaterinburg', 'pending',
                '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
            )
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO scheduler_jobs (
                    job_id, job_type, week_number, scheduled_for, timezone, status,
                    created_at, updated_at
                )
                VALUES (
                    'job-duplicate', 'week_close', 3, '2026-07-05T23:59:00+05:00',
                    'Asia/Yekaterinburg', 'pending',
                    '2026-07-01T10:00:00+05:00', '2026-07-01T10:00:00+05:00'
                )
                """
            )

        connection.execute(
            """
            INSERT INTO job_runs (
                job_id, job_type, week_number, started_at, status, idempotency_key
            )
            VALUES (
                'job-1', 'week_close', 3, '2026-07-05T23:59:00+05:00',
                'running', 'week-close:3'
            )
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO job_runs (
                    job_id, job_type, week_number, started_at, status, idempotency_key
                )
                VALUES (
                    'job-1', 'week_close', 3, '2026-07-05T23:59:01+05:00',
                    'running', 'week-close:3'
                )
                """
            )

        connection.execute(
            """
            INSERT INTO reminder_log (
                participant_id, team_id, week_number, reminder_type, sent_at, status
            )
            VALUES (
                'P001', 'T001', 3, 'sunday_2300', '2026-07-05T23:00:00+05:00',
                'sent'
            )
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO reminder_log (
                    participant_id, team_id, week_number, reminder_type, sent_at, status
                )
                VALUES (
                    'P001', 'T001', 3, 'sunday_2300', '2026-07-05T23:00:01+05:00',
                    'sent'
                )
                """
            )


def test_schema_has_lookup_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)

    indexes = list_indexes(db_path)

    expected_indexes = {
        "idx_dialog_states_telegram_id",
        "idx_draft_sessions_participant_id",
        "idx_draft_sessions_telegram_id",
        "idx_draft_sessions_expires_at",
        "idx_draft_messages_draft_id",
        "idx_scheduler_jobs_status_scheduled_for",
        "idx_reminder_log_participant_week_status",
        "idx_error_events_created_at",
        "idx_error_events_severity_admin_notified",
    }
    assert expected_indexes <= indexes


def test_schema_contains_insight_draft_technical_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("PRAGMA table_info(draft_insights)").fetchall()

    columns = {row[1] for row in rows}
    assert {"insight_title", "saved_insight_id", "saved_at"} <= columns
