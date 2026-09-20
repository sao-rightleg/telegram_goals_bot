"""SQLite technical drafts for participant planned-step setup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class StepDraftItem:
    step_number: int
    description: str
    metric: str | None


@dataclass(frozen=True)
class StepDraft:
    telegram_id: int
    participant_id: str
    flow_id: str
    goal_id: str
    status: str
    created_at: str
    updated_at: str
    expires_at: str
    items: tuple[StepDraftItem, ...]


class StepDraftRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def create(
        self, *, telegram_id: int, participant_id: str, flow_id: str,
        goal_id: str, occurred_at: str,
    ) -> StepDraft:
        expires_at = (datetime.fromisoformat(occurred_at) + timedelta(days=14)).isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM step_setup_drafts WHERE telegram_id = ?", (telegram_id,))
            connection.execute(
                """INSERT INTO step_setup_drafts (
                    telegram_id, participant_id, flow_id, goal_id, status,
                    created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)""",
                (telegram_id, participant_id, flow_id, goal_id, occurred_at, occurred_at, expires_at),
            )
        return self.get(telegram_id)  # type: ignore[return-value]

    def get(self, telegram_id: int) -> StepDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM step_setup_drafts WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
            if row is None:
                return None
            item_rows = connection.execute(
                """SELECT step_number, description, metric
                FROM step_setup_items WHERE telegram_id = ? ORDER BY step_number""",
                (telegram_id,),
            ).fetchall()
        return StepDraft(
            **dict(row),
            items=tuple(StepDraftItem(**dict(item)) for item in item_rows),
        )

    def set_description(
        self, telegram_id: int, *, step_number: int, description: str, occurred_at: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO step_setup_items (telegram_id, step_number, description, metric)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT(telegram_id, step_number) DO UPDATE SET
                    description=excluded.description, metric=NULL""",
                (telegram_id, step_number, description),
            )
            connection.execute(
                "UPDATE step_setup_drafts SET updated_at=? WHERE telegram_id=? AND status='active'",
                (occurred_at, telegram_id),
            )

    def set_metric(
        self, telegram_id: int, *, step_number: int, metric: str, occurred_at: str,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE step_setup_items SET metric=?
                WHERE telegram_id=? AND step_number=?""",
                (metric, telegram_id, step_number),
            )
            if cursor.rowcount != 1:
                raise KeyError("Step draft description not found")
            connection.execute(
                "UPDATE step_setup_drafts SET updated_at=? WHERE telegram_id=? AND status='active'",
                (occurred_at, telegram_id),
            )

    def claim(self, telegram_id: int, *, occurred_at: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE step_setup_drafts SET status='finalizing', updated_at=?
                WHERE telegram_id=? AND status='active'""",
                (occurred_at, telegram_id),
            )
        return cursor.rowcount == 1

    def release(self, telegram_id: int, *, occurred_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """UPDATE step_setup_drafts SET status='active', updated_at=?
                WHERE telegram_id=? AND status='finalizing'""",
                (occurred_at, telegram_id),
            )

    def recover_stale_finalization(
        self, telegram_id: int, *, stale_before: str, occurred_at: str
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """UPDATE step_setup_drafts SET status='active', updated_at=?
                WHERE telegram_id=? AND status='finalizing' AND updated_at < ?""",
                (occurred_at, telegram_id, stale_before),
            )
        return cursor.rowcount == 1

    def clear(self, telegram_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM step_setup_drafts WHERE telegram_id=?", (telegram_id,))

    def purge_expired(self, *, occurred_at: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM step_setup_drafts WHERE expires_at < ?", (occurred_at,)
            )
        return cursor.rowcount

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
