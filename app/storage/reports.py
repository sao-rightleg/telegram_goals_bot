"""SQLite repository for report generation and delivery state."""

from __future__ import annotations

from pathlib import Path
import sqlite3


class ReportStateRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def start_job_run(
        self,
        *,
        week_number: int,
        idempotency_key: str,
        started_at: str,
    ) -> int:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO report_job_runs (
                    week_number, job_type, idempotency_key, started_at, status
                )
                VALUES (?, 'report_generate_send', ?, ?, 'running')
                """,
                (week_number, idempotency_key, started_at),
            )
            row = connection.execute(
                "SELECT report_job_run_id FROM report_job_runs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
        return int(row[0])

    def finish_job_run(
        self,
        report_job_run_id: int,
        *,
        status: str,
        finished_at: str,
        error_message: str | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            cursor = connection.execute(
                """
                UPDATE report_job_runs
                SET status = ?, finished_at = ?, error_message = ?
                WHERE report_job_run_id = ?
                """,
                (status, finished_at, _sanitize_error_message(error_message), report_job_run_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"Report job run not found: {report_job_run_id}")

    def has_successful_delivery(
        self,
        *,
        week_number: int,
        report_type: str,
        scope_id: str,
        recipient_type: str,
        recipient_id: str,
    ) -> bool:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM report_delivery_log
                WHERE week_number = ?
                    AND report_type = ?
                    AND scope_id = ?
                    AND recipient_type = ?
                    AND recipient_id = ?
                    AND status = 'sent'
                """,
                (week_number, report_type, scope_id, recipient_type, recipient_id),
            ).fetchone()
        return row is not None

    def record_delivery_attempt(
        self,
        *,
        week_number: int,
        report_type: str,
        scope_id: str,
        recipient_type: str,
        recipient_id: str,
        chat_id: str,
        status: str,
        sent_at: str,
        telegram_message_id: int | None = None,
        file_path: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                """
                INSERT INTO report_delivery_log (
                    week_number, report_type, scope_id, recipient_type, recipient_id,
                    chat_id, status, sent_at, telegram_message_id, file_path,
                    error_message, attempt_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(week_number, report_type, scope_id, recipient_type, recipient_id)
                DO UPDATE SET
                    chat_id = excluded.chat_id,
                    status = excluded.status,
                    sent_at = excluded.sent_at,
                    telegram_message_id = excluded.telegram_message_id,
                    file_path = excluded.file_path,
                    error_message = excluded.error_message,
                    attempt_count = report_delivery_log.attempt_count + 1
                """,
                (
                    week_number,
                    report_type,
                    scope_id,
                    recipient_type,
                    recipient_id,
                    chat_id,
                    status,
                    sent_at,
                    telegram_message_id,
                    file_path,
                    _sanitize_error_message(error_message),
                ),
            )


def _sanitize_error_message(message: str | None) -> str | None:
    if not message:
        return None
    compact = " ".join(str(message).split())
    redacted = compact.replace("token=", "redacted=")
    return redacted[:240]
