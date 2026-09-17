"""SQLite technical state for manual RUPOR broadcasts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class RuporDraft:
    operator_telegram_id: int
    broadcast_id: str
    message_text: str | None
    status: str
    created_at: str
    updated_at: str


class RuporRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def save_draft(self, draft: RuporDraft) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rupor_drafts (
                    operator_telegram_id, broadcast_id, message_text, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(operator_telegram_id) DO UPDATE SET
                    broadcast_id = excluded.broadcast_id,
                    message_text = excluded.message_text,
                    status = excluded.status,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    draft.operator_telegram_id,
                    draft.broadcast_id,
                    draft.message_text,
                    draft.status,
                    draft.created_at,
                    draft.updated_at,
                ),
            )

    def get_draft(self, operator_telegram_id: int) -> RuporDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM rupor_drafts WHERE operator_telegram_id = ?",
                (operator_telegram_id,),
            ).fetchone()
        return RuporDraft(**dict(row)) if row is not None else None

    def list_sending_drafts(self) -> list[RuporDraft]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM rupor_drafts WHERE status = 'sending' AND message_text IS NOT NULL"
            ).fetchall()
        return [RuporDraft(**dict(row)) for row in rows]

    def claim_broadcast(self, operator_telegram_id: int, *, broadcast_id: str, updated_at: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE rupor_drafts SET status = 'sending', updated_at = ?
                WHERE operator_telegram_id = ? AND broadcast_id = ? AND status = 'draft'
                """,
                (updated_at, operator_telegram_id, broadcast_id),
            )
        return cursor.rowcount == 1

    def finish_broadcast(self, operator_telegram_id: int, *, broadcast_id: str, updated_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE rupor_drafts
                SET status = 'sent', message_text = NULL, updated_at = ?
                WHERE operator_telegram_id = ? AND broadcast_id = ? AND status = 'sending'
                """,
                (updated_at, operator_telegram_id, broadcast_id),
            )

    def cancel_broadcast(self, operator_telegram_id: int, *, broadcast_id: str, updated_at: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE rupor_drafts
                SET status = 'cancelled', message_text = NULL, updated_at = ?
                WHERE operator_telegram_id = ? AND broadcast_id = ? AND status = 'draft'
                """,
                (updated_at, operator_telegram_id, broadcast_id),
            )
        return cursor.rowcount == 1

    def ensure_delivery(self, broadcast_id: str, participant_id: str, *, updated_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO rupor_deliveries (
                    broadcast_id, participant_id, status, error_type, updated_at
                ) VALUES (?, ?, 'pending', NULL, ?)
                """,
                (broadcast_id, participant_id, updated_at),
            )

    def list_delivery_participant_ids(self, broadcast_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT participant_id FROM rupor_deliveries
                WHERE broadcast_id = ? ORDER BY participant_id
                """,
                (broadcast_id,),
            ).fetchall()
        return [str(row["participant_id"]) for row in rows]

    def delivery_counts(self, broadcast_id: str) -> dict[str, int]:
        counts = {"pending": 0, "sent": 0, "failed": 0, "skipped": 0, "unknown": 0}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status, COUNT(*) AS count FROM rupor_deliveries
                WHERE broadcast_id = ? GROUP BY status
                """,
                (broadcast_id,),
            ).fetchall()
        for row in rows:
            counts[str(row["status"])] = int(row["count"])
        return counts

    def mark_delivery(
        self,
        broadcast_id: str,
        participant_id: str,
        *,
        status: str,
        error_type: str | None,
        updated_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE rupor_deliveries SET status = ?, error_type = ?, updated_at = ?
                WHERE broadcast_id = ? AND participant_id = ? AND status != 'sent'
                """,
                (status, error_type, updated_at, broadcast_id, participant_id),
            )

    def delivery_status(self, broadcast_id: str, participant_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM rupor_deliveries
                WHERE broadcast_id = ? AND participant_id = ?
                """,
                (broadcast_id, participant_id),
            ).fetchone()
        return str(row["status"]) if row is not None else None

    def expire_drafts_before(self, cutoff: str, *, occurred_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE rupor_drafts
                SET status = 'cancelled', message_text = NULL, updated_at = ?
                WHERE status IN ('draft', 'sending') AND updated_at < ?
                """,
                (occurred_at, cutoff),
            )
        return cursor.rowcount

    def add_audit(
        self,
        *,
        operator_telegram_id: int,
        broadcast_id: str | None,
        action: str,
        occurred_at: str,
        details: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rupor_audit_log (
                    operator_telegram_id, broadcast_id, action, details, occurred_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (operator_telegram_id, broadcast_id, action, details, occurred_at),
            )

    def list_audit_actions(self, operator_telegram_id: int) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT action FROM rupor_audit_log
                WHERE operator_telegram_id = ? ORDER BY audit_id
                """,
                (operator_telegram_id,),
            ).fetchall()
        return [str(row["action"]) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
