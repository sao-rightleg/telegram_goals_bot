"""SQLite technical-state schema initialization and inspection helpers."""

from __future__ import annotations

from pathlib import Path
import sqlite3


REQUIRED_TECHNICAL_TABLES = {
    "draft_sessions",
    "dialog_states",
    "draft_messages",
    "draft_attachments",
    "draft_reports",
    "draft_insights",
    "scheduler_jobs",
    "job_runs",
    "reminder_log",
    "error_events",
}

BUSINESS_PRIMARY_TABLES = {
    "participants",
    "teams",
    "trackers",
    "goals",
    "planned_steps",
    "weekly_reports",
    "weekly_report_steps",
    "insights",
    "report_runs",
    "consent",
}


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS draft_sessions (
        draft_id TEXT PRIMARY KEY,
        draft_type TEXT NOT NULL CHECK (
            draft_type IN ('weekly_report', 'insight', 'captain_manual_report')
        ),
        participant_id TEXT NOT NULL,
        telegram_id INTEGER NOT NULL,
        flow_source TEXT NOT NULL CHECK (
            flow_source IN ('participant_bot', 'captain_manual')
        ),
        status TEXT NOT NULL CHECK (
            status IN ('active', 'saving', 'saved', 'failed', 'expired')
        ),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dialog_states (
        telegram_id INTEGER PRIMARY KEY,
        participant_id TEXT,
        role TEXT CHECK (
            role IS NULL OR role IN ('participant', 'captain', 'tracker', 'admin', 'sitnikov')
        ),
        flow TEXT NOT NULL CHECK (
            flow IN (
                'consent',
                'weekly_report',
                'insight',
                'captain_manual_report',
                'view_goal',
                'view_steps',
                'view_progress',
                'view_team',
                'idle'
            )
        ),
        step TEXT NOT NULL,
        week_number INTEGER CHECK (week_number IS NULL OR week_number BETWEEN 1 AND 8),
        selected_status TEXT CHECK (
            selected_status IS NULL OR selected_status IN ('green', 'blue', 'red', 'gray')
        ),
        selected_participant_id TEXT,
        selected_step_ids TEXT,
        draft_id TEXT,
        started_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT,
        FOREIGN KEY (draft_id) REFERENCES draft_sessions(draft_id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS draft_messages (
        draft_message_id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        telegram_id INTEGER NOT NULL,
        message_order INTEGER NOT NULL CHECK (message_order > 0),
        message_type TEXT NOT NULL CHECK (
            message_type IN ('text', 'voice_transcription', 'system_note')
        ),
        text TEXT NOT NULL,
        telegram_message_id INTEGER,
        created_at TEXT NOT NULL,
        UNIQUE (draft_id, message_order),
        FOREIGN KEY (draft_id) REFERENCES draft_sessions(draft_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS draft_attachments (
        draft_attachment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id TEXT NOT NULL,
        participant_id TEXT NOT NULL,
        telegram_file_id TEXT NOT NULL,
        local_file_path TEXT NOT NULL,
        duration_seconds INTEGER NOT NULL CHECK (
            duration_seconds >= 0 AND duration_seconds <= 600
        ),
        transcription_status TEXT NOT NULL CHECK (
            transcription_status IN ('pending', 'success', 'failed')
        ),
        transcription_text TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (draft_id) REFERENCES draft_sessions(draft_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS draft_reports (
        draft_id TEXT PRIMARY KEY,
        participant_id TEXT NOT NULL,
        team_id TEXT NOT NULL,
        goal_id TEXT NOT NULL,
        week_number INTEGER NOT NULL CHECK (week_number BETWEEN 1 AND 8),
        flow_source TEXT NOT NULL CHECK (
            flow_source IN ('participant_bot', 'captain_manual')
        ),
        status_code TEXT NOT NULL CHECK (status_code IN ('green', 'blue', 'red', 'gray')),
        status_symbol TEXT NOT NULL CHECK (status_symbol IN ('🟩', '🟦', '🟥', '⬜')),
        submitted_by_id TEXT NOT NULL,
        submitted_by_role TEXT NOT NULL CHECK (
            submitted_by_role IN ('participant', 'captain', 'admin', 'system')
        ),
        selected_step_ids TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (draft_id) REFERENCES draft_sessions(draft_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS draft_insights (
        draft_id TEXT PRIMARY KEY,
        participant_id TEXT NOT NULL,
        goal_id TEXT NOT NULL,
        week_number INTEGER CHECK (week_number IS NULL OR week_number BETWEEN 1 AND 8),
        insight_scope TEXT NOT NULL CHECK (
            insight_scope IN ('current_week', 'previous_week', 'goal_general')
        ),
        created_by_id TEXT NOT NULL,
        created_by_role TEXT NOT NULL CHECK (
            created_by_role IN ('participant', 'captain', 'admin')
        ),
        insight_title TEXT,
        saved_insight_id TEXT,
        saved_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (draft_id) REFERENCES draft_sessions(draft_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scheduler_jobs (
        job_id TEXT PRIMARY KEY,
        job_type TEXT NOT NULL CHECK (
            job_type IN (
                'monday_reminder',
                'wednesday_checkin',
                'sunday_1800_checkin',
                'sunday_2230_reminder',
                'sunday_2300_reminder',
                'week_close',
                'report_generate',
                'report_send',
                'audio_cleanup',
                'sqlite_backup',
                'google_sheets_export',
                'pdf_retention_check'
            )
        ),
        week_number INTEGER CHECK (week_number IS NULL OR week_number BETWEEN 1 AND 8),
        scheduled_for TEXT NOT NULL,
        timezone TEXT NOT NULL CHECK (timezone = 'Asia/Yekaterinburg'),
        status TEXT NOT NULL CHECK (
            status IN ('pending', 'running', 'completed', 'failed', 'skipped')
        ),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE (job_type, week_number, scheduled_for)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS job_runs (
        job_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        job_type TEXT NOT NULL,
        week_number INTEGER CHECK (week_number IS NULL OR week_number BETWEEN 1 AND 8),
        started_at TEXT NOT NULL,
        finished_at TEXT,
        status TEXT NOT NULL CHECK (
            status IN ('running', 'completed', 'failed', 'skipped')
        ),
        idempotency_key TEXT NOT NULL UNIQUE,
        error_message TEXT,
        FOREIGN KEY (job_id) REFERENCES scheduler_jobs(job_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reminder_log (
        reminder_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        participant_id TEXT NOT NULL,
        team_id TEXT NOT NULL,
        week_number INTEGER NOT NULL CHECK (week_number BETWEEN 1 AND 8),
        reminder_type TEXT NOT NULL CHECK (
            reminder_type IN (
                'monday_start',
                'wednesday_checkin',
                'sunday_1800',
                'sunday_2230',
                'sunday_2300'
            )
        ),
        sent_at TEXT NOT NULL,
        telegram_message_id INTEGER,
        status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
        error_message TEXT,
        UNIQUE (participant_id, week_number, reminder_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS error_events (
        error_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        module TEXT NOT NULL,
        error_type TEXT NOT NULL,
        severity TEXT NOT NULL CHECK (
            severity IN ('critical', 'high', 'medium', 'low')
        ),
        participant_id TEXT,
        team_id TEXT,
        message TEXT NOT NULL,
        admin_notified INTEGER NOT NULL DEFAULT 0 CHECK (admin_notified IN (0, 1)),
        resolved INTEGER NOT NULL DEFAULT 0 CHECK (resolved IN (0, 1))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_dialog_states_telegram_id ON dialog_states(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_draft_sessions_participant_id ON draft_sessions(participant_id)",
    "CREATE INDEX IF NOT EXISTS idx_draft_sessions_telegram_id ON draft_sessions(telegram_id)",
    "CREATE INDEX IF NOT EXISTS idx_draft_sessions_expires_at ON draft_sessions(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_draft_messages_draft_id ON draft_messages(draft_id)",
    "CREATE INDEX IF NOT EXISTS idx_draft_attachments_draft_id ON draft_attachments(draft_id)",
    "CREATE INDEX IF NOT EXISTS idx_scheduler_jobs_status_scheduled_for ON scheduler_jobs(status, scheduled_for)",
    "CREATE INDEX IF NOT EXISTS idx_reminder_log_participant_week_status ON reminder_log(participant_id, week_number, status)",
    "CREATE INDEX IF NOT EXISTS idx_error_events_created_at ON error_events(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_error_events_severity_admin_notified ON error_events(severity, admin_notified)",
    """
    CREATE TRIGGER IF NOT EXISTS trg_draft_messages_require_session
    BEFORE INSERT ON draft_messages
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM draft_sessions WHERE draft_id = NEW.draft_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'draft_messages.draft_id must reference draft_sessions');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_draft_attachments_require_session
    BEFORE INSERT ON draft_attachments
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM draft_sessions WHERE draft_id = NEW.draft_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'draft_attachments.draft_id must reference draft_sessions');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_draft_reports_require_session
    BEFORE INSERT ON draft_reports
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM draft_sessions WHERE draft_id = NEW.draft_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'draft_reports.draft_id must reference draft_sessions');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_draft_insights_require_session
    BEFORE INSERT ON draft_insights
    FOR EACH ROW
    WHEN NOT EXISTS (
        SELECT 1 FROM draft_sessions WHERE draft_id = NEW.draft_id
    )
    BEGIN
        SELECT RAISE(ABORT, 'draft_insights.draft_id must reference draft_sessions');
    END
    """,
]


def initialize_schema(db_path: str | Path) -> None:
    """Create or update the SQLite technical-state schema."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_columns(
            connection,
            "draft_insights",
            {
                "insight_title": "TEXT",
                "saved_insight_id": "TEXT",
                "saved_at": "TEXT",
            },
        )


def list_tables(db_path: str | Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
    return {row[0] for row in rows}


def list_indexes(db_path: str | Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index' AND name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
    return {row[0] for row in rows}


def _ensure_columns(
    connection: sqlite3.Connection,
    table_name: str,
    columns: dict[str, str],
) -> None:
    existing = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    for column_name, definition in columns.items():
        if column_name not in existing:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
