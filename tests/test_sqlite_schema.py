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


def test_report_tables_are_technical_not_business_primary(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)

    tables = list_tables(db_path)
    assert {"report_job_runs", "report_delivery_log"} <= tables
    assert "report_runs" not in tables
    assert "report_job_runs" not in BUSINESS_PRIMARY_TABLES
    assert "report_delivery_log" not in BUSINESS_PRIMARY_TABLES


def test_init_does_not_create_business_primary_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_init_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)
    initialize_schema(db_path)

    assert REQUIRED_TECHNICAL_TABLES <= list_tables(db_path)


def test_init_migrates_legacy_dialog_flow_constraint_for_registration(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE dialog_states")
        connection.execute(
            """
            CREATE TABLE dialog_states (
                telegram_id INTEGER PRIMARY KEY,
                participant_id TEXT,
                role TEXT,
                flow TEXT NOT NULL CHECK (flow IN ('consent', 'idle')),
                step TEXT NOT NULL,
                week_number INTEGER,
                selected_status TEXT,
                selected_participant_id TEXT,
                selected_step_ids TEXT,
                draft_id TEXT,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO draft_sessions (
                draft_id, draft_type, participant_id, telegram_id, flow_source,
                status, created_at, updated_at
            ) VALUES (
                'draft-before', 'weekly_report', 'P001', 1001, 'participant_bot',
                'active', 'before-start', 'before-update'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO dialog_states (
                telegram_id, participant_id, role, flow, step, week_number,
                selected_status, selected_participant_id, selected_step_ids,
                draft_id, started_at, updated_at, expires_at
            ) VALUES (
                1001, 'P001', 'participant', 'idle', 'menu', 3,
                'blue', 'P002', '["S001"]', 'draft-before',
                'before-start', 'before-update', 'before-expiry'
            )
            """
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO dialog_states (
                    telegram_id, flow, step, started_at, updated_at
                ) VALUES (1002, 'registration', 'awaiting_first_name', 'now', 'now')
                """
            )

    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO dialog_states (
                telegram_id, flow, step, started_at, updated_at
            ) VALUES (1002, 'registration', 'awaiting_first_name', 'now', 'now')
            """
        )
        preserved = connection.execute(
            "SELECT * FROM dialog_states WHERE telegram_id = 1001"
        ).fetchone()

    assert preserved == (
        1001, "P001", "participant", "idle", "menu", 3, "blue", "P002",
        '["S001"]', "draft-before", "before-start", "before-update", "before-expiry",
    )
    initialize_schema(db_path)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM dialog_states").fetchone()[0] == 2
    assert "idx_dialog_states_telegram_id" in list_indexes(db_path)


def test_dialog_states_migration_rolls_back_on_rebuild_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "state.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE dialog_states (
                telegram_id INTEGER PRIMARY KEY,
                flow TEXT NOT NULL CHECK (flow IN ('idle')),
                step TEXT NOT NULL,
                started_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO dialog_states VALUES (1001, 'idle', 'menu', 'before', 'before')"
        )

    original_connect = sqlite3.connect

    class FailingConnection:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self.connection = connection

        def __enter__(self):
            self.connection.__enter__()
            return self

        def __exit__(self, *args):
            return self.connection.__exit__(*args)

        def execute(self, sql: str, parameters=()):
            if sql == "DROP TABLE dialog_states":
                raise RuntimeError("injected migration failure")
            return self.connection.execute(sql, parameters)

    monkeypatch.setattr(
        "app.storage.sqlite.sqlite3.connect",
        lambda path: FailingConnection(original_connect(path)),
    )
    with pytest.raises(RuntimeError, match="injected migration failure"):
        initialize_schema(db_path)
    monkeypatch.undo()

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT * FROM dialog_states").fetchone() == (
            1001, "idle", "menu", "before", "before"
        )
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name = 'dialog_states_migrated'"
        ).fetchone()[0] == 0

    initialize_schema(db_path)


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


def test_reminder_log_tracks_attempt_count(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"

    initialize_schema(db_path)
    initialize_schema(db_path)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("PRAGMA table_info(reminder_log)").fetchall()

    columns = {row[1] for row in rows}
    assert "attempt_count" in columns
