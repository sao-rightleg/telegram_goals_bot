"""Repository for SQLite technical dialog state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class DialogState:
    telegram_id: int
    participant_id: str | None
    role: str | None
    flow: str
    step: str
    started_at: str
    updated_at: str
    week_number: int | None = None
    selected_status: str | None = None
    selected_participant_id: str | None = None
    selected_step_ids: str | None = None
    draft_id: str | None = None
    expires_at: str | None = None


class DialogStateRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def upsert(self, state: DialogState) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO dialog_states (
                    telegram_id,
                    participant_id,
                    role,
                    flow,
                    step,
                    week_number,
                    selected_status,
                    selected_participant_id,
                    selected_step_ids,
                    draft_id,
                    started_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    participant_id = excluded.participant_id,
                    role = excluded.role,
                    flow = excluded.flow,
                    step = excluded.step,
                    week_number = excluded.week_number,
                    selected_status = excluded.selected_status,
                    selected_participant_id = excluded.selected_participant_id,
                    selected_step_ids = excluded.selected_step_ids,
                    draft_id = excluded.draft_id,
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    state.telegram_id,
                    state.participant_id,
                    state.role,
                    state.flow,
                    state.step,
                    state.week_number,
                    state.selected_status,
                    state.selected_participant_id,
                    state.selected_step_ids,
                    state.draft_id,
                    state.started_at,
                    state.updated_at,
                    state.expires_at,
                ),
            )

    def get(self, telegram_id: int) -> DialogState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    telegram_id,
                    participant_id,
                    role,
                    flow,
                    step,
                    week_number,
                    selected_status,
                    selected_participant_id,
                    selected_step_ids,
                    draft_id,
                    started_at,
                    updated_at,
                    expires_at
                FROM dialog_states
                WHERE telegram_id = ?
                """,
                (telegram_id,),
            ).fetchone()

        if row is None:
            return None
        return DialogState(**dict(row))

    def clear(self, telegram_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM dialog_states WHERE telegram_id = ?", (telegram_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
