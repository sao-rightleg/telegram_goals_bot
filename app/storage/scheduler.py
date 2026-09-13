"""SQLite repositories for scheduler technical state."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from app.scheduler.calendar import TIMEZONE_NAME


class SchedulerJobRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def start_job_run(
        self,
        *,
        job_type: str,
        week_number: int | None,
        scheduled_for: str,
        idempotency_key: str,
        started_at: str,
    ) -> int:
        job_id = _job_id(job_type, week_number, scheduled_for)
        with sqlite3.connect(self._db_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO scheduler_jobs (
                    job_id, job_type, week_number, scheduled_for, timezone, status,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'running', ?, ?)
                ON CONFLICT(job_type, week_number, scheduled_for) DO UPDATE SET
                    status = 'running',
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    job_type,
                    week_number,
                    scheduled_for,
                    TIMEZONE_NAME,
                    started_at,
                    started_at,
                ),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO job_runs (
                    job_id, job_type, week_number, started_at, status, idempotency_key
                )
                VALUES (?, ?, ?, ?, 'running', ?)
                """,
                (job_id, job_type, week_number, started_at, idempotency_key),
            )
            row = connection.execute(
                "SELECT job_run_id FROM job_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return int(row[0])

    def finish_job_run(
        self,
        job_run_id: int,
        *,
        status: str,
        finished_at: str,
        error_message: str | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                "SELECT job_id FROM job_runs WHERE job_run_id = ?",
                (job_run_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Job run not found: {job_run_id}")

            job_id = str(row[0])
            connection.execute(
                """
                UPDATE job_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE job_run_id = ?
                """,
                (status, finished_at, error_message, job_run_id),
            )
            connection.execute(
                """
                UPDATE scheduler_jobs
                SET status = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, finished_at, job_id),
            )

    def has_successful_reminder(
        self,
        participant_id: str,
        *,
        week_number: int,
        reminder_type: str,
    ) -> bool:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM reminder_log
                WHERE participant_id = ?
                    AND week_number = ?
                    AND reminder_type = ?
                    AND status = 'sent'
                """,
                (participant_id, week_number, reminder_type),
            ).fetchone()
        return row is not None

    def record_reminder_attempt(
        self,
        *,
        participant_id: str,
        team_id: str,
        week_number: int,
        reminder_type: str,
        sent_at: str,
        status: str,
        telegram_message_id: int | None = None,
        error_message: str | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO reminder_log (
                    participant_id, team_id, week_number, reminder_type, sent_at,
                    telegram_message_id, status, attempt_count, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(participant_id, week_number, reminder_type) DO UPDATE SET
                    team_id = excluded.team_id,
                    sent_at = excluded.sent_at,
                    telegram_message_id = excluded.telegram_message_id,
                    status = excluded.status,
                    attempt_count = reminder_log.attempt_count + 1,
                    error_message = excluded.error_message
                """,
                (
                    participant_id,
                    team_id,
                    week_number,
                    reminder_type,
                    sent_at,
                    telegram_message_id,
                    status,
                    error_message,
                ),
            )

    def record_error(
        self,
        *,
        module: str,
        error_type: str,
        severity: str,
        message: str,
        created_at: str,
        participant_id: str | None = None,
        team_id: str | None = None,
        admin_notified: bool = False,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO error_events (
                    created_at, module, error_type, severity, participant_id,
                    team_id, message, admin_notified
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    module,
                    error_type,
                    severity,
                    participant_id,
                    team_id,
                    message,
                    1 if admin_notified else 0,
                ),
            )

    def has_successful_event_delivery(
        self,
        event_id: str,
        recipient_id: str,
        *,
        week_number: int | None,
    ) -> bool:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM scheduled_event_deliveries
                WHERE event_id = ?
                    AND recipient_id = ?
                    AND week_number IS ?
                    AND status = 'sent'
                """,
                (event_id, recipient_id, week_number),
            ).fetchone()
        return row is not None

    def claim_event_delivery(
        self,
        *,
        event_id: str,
        recipient_id: str,
        week_number: int | None,
        scheduled_for: str,
        updated_at: str,
        stale_before: str | None = None,
    ) -> bool:
        """Atomically reserve one event/recipient delivery, including failed retries."""

        with sqlite3.connect(self._db_path) as connection:
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO scheduled_event_deliveries (
                    event_id, recipient_id, week_number, scheduled_for, status,
                    attempt_count, updated_at
                )
                VALUES (?, ?, ?, ?, 'pending', 1, ?)
                """,
                (event_id, recipient_id, week_number, scheduled_for, updated_at),
            )
            if inserted.rowcount == 1:
                return True
            retried = connection.execute(
                """
                UPDATE scheduled_event_deliveries
                SET status = 'pending', scheduled_for = ?,
                    attempt_count = attempt_count + 1, error_message = NULL, updated_at = ?
                WHERE event_id = ? AND recipient_id = ? AND week_number IS ?
                    AND (
                        status = 'failed'
                        OR (status = 'pending' AND ? IS NOT NULL AND updated_at < ?)
                    )
                """,
                (
                    scheduled_for,
                    updated_at,
                    event_id,
                    recipient_id,
                    week_number,
                    stale_before,
                    stale_before,
                ),
            )
            return retried.rowcount == 1

    def record_event_delivery(
        self,
        *,
        event_id: str,
        recipient_id: str,
        week_number: int | None,
        scheduled_for: str,
        status: str,
        updated_at: str,
        error_message: str | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO scheduled_event_deliveries (
                    event_id, recipient_id, week_number, scheduled_for, status,
                    attempt_count, error_message, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(event_id, recipient_id, week_number) DO UPDATE SET
                    scheduled_for = excluded.scheduled_for,
                    status = excluded.status,
                    error_message = excluded.error_message,
                    updated_at = excluded.updated_at
                """,
                (
                    event_id,
                    recipient_id,
                    week_number,
                    scheduled_for,
                    status,
                    error_message,
                    updated_at,
                ),
            )


def _job_id(job_type: str, week_number: int | None, scheduled_for: str) -> str:
    week_part = "none" if week_number is None else f"week-{week_number:02d}"
    return f"{job_type}:{week_part}:{scheduled_for}"
