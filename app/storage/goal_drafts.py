"""SQLite technical drafts for participant goal creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class GoalDraft:
    telegram_id: int
    participant_id: str
    flow_id: str
    status: str
    goal_title: str | None
    goal_description: str | None
    goal_value_amount: str | None
    goal_value_currency: str | None
    permission_condition: str | None
    created_at: str
    updated_at: str
    expires_at: str


class GoalDraftRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def create(self, *, telegram_id: int, participant_id: str, flow_id: str, occurred_at: str) -> GoalDraft:
        expires_at = (datetime.fromisoformat(occurred_at) + timedelta(days=7)).isoformat()
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO goal_drafts (
                    telegram_id, participant_id, flow_id, status, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, 'active', ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    participant_id=excluded.participant_id, flow_id=excluded.flow_id,
                    status='active', goal_title=NULL, goal_description=NULL,
                    goal_value_amount=NULL, goal_value_currency=NULL,
                    permission_condition=NULL, created_at=excluded.created_at,
                    updated_at=excluded.updated_at, expires_at=excluded.expires_at""",
                (telegram_id, participant_id, flow_id, occurred_at, occurred_at, expires_at),
            )
        return self.get(telegram_id)  # type: ignore[return-value]

    def get(self, telegram_id: int) -> GoalDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM goal_drafts WHERE telegram_id = ?", (telegram_id,)
            ).fetchone()
        return GoalDraft(**dict(row)) if row else None

    def update(self, telegram_id: int, *, field: str, value: str, occurred_at: str) -> GoalDraft:
        allowed = {
            "goal_title", "goal_description", "goal_value_amount",
            "goal_value_currency", "permission_condition",
        }
        if field not in allowed:
            raise ValueError("Unsupported goal draft field")
        with self._connect() as connection:
            connection.execute(
                f"UPDATE goal_drafts SET {field} = ?, updated_at = ? "
                "WHERE telegram_id = ? AND status = 'active'",
                (value, occurred_at, telegram_id),
            )
        draft = self.get(telegram_id)
        if draft is None:
            raise KeyError("Goal draft not found")
        return draft

    def claim(self, telegram_id: int, *, occurred_at: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE goal_drafts SET status='finalizing', updated_at=? "
                "WHERE telegram_id=? AND status='active'",
                (occurred_at, telegram_id),
            )
        return cursor.rowcount == 1

    def release(self, telegram_id: int, *, occurred_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE goal_drafts SET status='active', updated_at=? "
                "WHERE telegram_id=? AND status='finalizing'",
                (occurred_at, telegram_id),
            )

    def clear(self, telegram_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM goal_drafts WHERE telegram_id = ?", (telegram_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
