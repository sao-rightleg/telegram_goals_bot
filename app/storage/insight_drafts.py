"""Repository for SQLite insight draft state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


_INSIGHT_SCOPE = "current_week"


@dataclass(frozen=True)
class InsightVoiceAttachment:
    local_file_path: str
    transcription_text: str
    duration_seconds: int


@dataclass(frozen=True)
class InsightDraft:
    draft_id: str
    telegram_id: int
    participant_id: str
    goal_id: str
    week_number: int
    insight_scope: str
    insight_title: str | None
    insight_text: str
    message_count: int
    created_at: str
    updated_at: str
    saved_insight_id: str | None = None
    saved_at: str | None = None
    expires_at: str | None = None
    voice_attachments: tuple[InsightVoiceAttachment, ...] = ()


class InsightDraftRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def create_draft(
        self,
        *,
        draft_id: str,
        telegram_id: int,
        participant_id: str,
        goal_id: str,
        week_number: int,
        occurred_at: str,
        expires_at: str | None = None,
    ) -> None:
        self.clear_draft(telegram_id)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO draft_sessions (
                    draft_id,
                    draft_type,
                    participant_id,
                    telegram_id,
                    flow_source,
                    status,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, 'insight', ?, ?, 'participant_bot', 'active', ?, ?, ?)
                """,
                (draft_id, participant_id, telegram_id, occurred_at, occurred_at, expires_at),
            )
            connection.execute(
                """
                INSERT INTO draft_insights (
                    draft_id,
                    participant_id,
                    goal_id,
                    week_number,
                    insight_scope,
                    created_by_id,
                    created_by_role,
                    insight_title,
                    saved_insight_id,
                    saved_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'participant', NULL, NULL, NULL, ?, ?)
                """,
                (
                    draft_id,
                    participant_id,
                    goal_id,
                    week_number,
                    _INSIGHT_SCOPE,
                    participant_id,
                    occurred_at,
                    occurred_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO dialog_states (
                    telegram_id,
                    participant_id,
                    role,
                    flow,
                    step,
                    week_number,
                    draft_id,
                    started_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, 'participant', 'insight', 'draft_started', ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    participant_id = excluded.participant_id,
                    role = excluded.role,
                    flow = excluded.flow,
                    step = excluded.step,
                    week_number = excluded.week_number,
                    selected_status = NULL,
                    selected_step_ids = NULL,
                    selected_participant_id = NULL,
                    draft_id = excluded.draft_id,
                    started_at = excluded.started_at,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    telegram_id,
                    participant_id,
                    week_number,
                    draft_id,
                    occurred_at,
                    occurred_at,
                    expires_at,
                ),
            )

    def append_text_message(
        self,
        telegram_id: int,
        text: str,
        *,
        occurred_at: str,
        telegram_message_id: int | None = None,
    ) -> None:
        draft = self.get_active_draft(telegram_id)
        if draft is None:
            raise KeyError(f"Active insight draft not found for telegram_id={telegram_id}")

        next_order = draft.message_count + 1
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO draft_messages (
                    draft_id,
                    participant_id,
                    telegram_id,
                    message_order,
                    message_type,
                    text,
                    telegram_message_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'text', ?, ?, ?)
                """,
                (
                    draft.draft_id,
                    draft.participant_id,
                    telegram_id,
                    next_order,
                    text,
                    telegram_message_id,
                    occurred_at,
                ),
            )
            self._touch(connection, draft.draft_id, telegram_id, occurred_at)

    def append_voice_transcription(
        self,
        telegram_id: int,
        *,
        telegram_file_id: str,
        local_file_path: str | Path,
        duration_seconds: int,
        transcription_text: str,
        occurred_at: str,
        telegram_message_id: int | None = None,
    ) -> None:
        draft = self.get_active_draft(telegram_id)
        if draft is None:
            raise KeyError(f"Active insight draft not found for telegram_id={telegram_id}")

        next_order = draft.message_count + 1
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO draft_attachments (
                    draft_id,
                    participant_id,
                    telegram_file_id,
                    local_file_path,
                    duration_seconds,
                    transcription_status,
                    transcription_text,
                    error_message,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'success', ?, NULL, ?, ?)
                """,
                (
                    draft.draft_id,
                    draft.participant_id,
                    telegram_file_id,
                    str(local_file_path),
                    duration_seconds,
                    transcription_text,
                    occurred_at,
                    occurred_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO draft_messages (
                    draft_id,
                    participant_id,
                    telegram_id,
                    message_order,
                    message_type,
                    text,
                    telegram_message_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'voice_transcription', ?, ?, ?)
                """,
                (
                    draft.draft_id,
                    draft.participant_id,
                    telegram_id,
                    next_order,
                    transcription_text,
                    telegram_message_id,
                    occurred_at,
                ),
            )
            self._touch(connection, draft.draft_id, telegram_id, occurred_at)

    def set_title(self, telegram_id: int, title: str, *, occurred_at: str) -> None:
        draft = self.get_active_draft(telegram_id)
        if draft is None:
            raise KeyError(f"Active insight draft not found for telegram_id={telegram_id}")

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE draft_insights
                SET insight_title = ?, updated_at = ?
                WHERE draft_id = ?
                """,
                (title, occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE draft_sessions SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE dialog_states SET step = 'title_set', updated_at = ? WHERE telegram_id = ?",
                (occurred_at, telegram_id),
            )

    def request_title(self, telegram_id: int, *, occurred_at: str) -> None:
        draft = self.get_active_draft(telegram_id)
        if draft is None:
            raise KeyError(f"Active insight draft not found for telegram_id={telegram_id}")

        with self._connect() as connection:
            connection.execute(
                "UPDATE draft_sessions SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE draft_insights SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE dialog_states SET step = 'awaiting_title', updated_at = ? WHERE telegram_id = ?",
                (occurred_at, telegram_id),
            )

    def mark_saved(self, telegram_id: int, *, saved_insight_id: str, saved_at: str) -> None:
        draft = self.get_active_draft(telegram_id)
        if draft is None:
            raise KeyError(f"Active insight draft not found for telegram_id={telegram_id}")

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE draft_sessions
                SET status = 'saved', updated_at = ?
                WHERE draft_id = ?
                """,
                (saved_at, draft.draft_id),
            )
            connection.execute(
                """
                UPDATE draft_insights
                SET saved_insight_id = ?, saved_at = ?, updated_at = ?
                WHERE draft_id = ?
                """,
                (saved_insight_id, saved_at, saved_at, draft.draft_id),
            )
            connection.execute("DELETE FROM draft_messages WHERE draft_id = ?", (draft.draft_id,))
            connection.execute("DELETE FROM draft_attachments WHERE draft_id = ?", (draft.draft_id,))
            connection.execute("DELETE FROM dialog_states WHERE telegram_id = ?", (telegram_id,))

    def get_active_draft(self, telegram_id: int) -> InsightDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sessions.draft_id,
                    sessions.telegram_id,
                    sessions.participant_id,
                    insights.goal_id,
                    insights.week_number,
                    insights.insight_scope,
                    insights.insight_title,
                    insights.saved_insight_id,
                    insights.saved_at,
                    sessions.created_at,
                    insights.updated_at,
                    sessions.expires_at
                FROM dialog_states AS dialog
                JOIN draft_sessions AS sessions ON sessions.draft_id = dialog.draft_id
                JOIN draft_insights AS insights ON insights.draft_id = sessions.draft_id
                WHERE
                    dialog.telegram_id = ?
                    AND dialog.flow = 'insight'
                    AND sessions.draft_type = 'insight'
                    AND sessions.status = 'active'
                """,
                (telegram_id,),
            ).fetchone()

            if row is None:
                return None

            draft_id = str(row["draft_id"])
            message_rows = self._message_rows(connection, draft_id)
            attachment_rows = self._attachment_rows(connection, draft_id)

        return _draft_from_row(row, message_rows, attachment_rows)

    def get_recent_saved_draft(self, telegram_id: int) -> InsightDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sessions.draft_id,
                    sessions.telegram_id,
                    sessions.participant_id,
                    insights.goal_id,
                    insights.week_number,
                    insights.insight_scope,
                    insights.insight_title,
                    insights.saved_insight_id,
                    insights.saved_at,
                    sessions.created_at,
                    insights.updated_at,
                    sessions.expires_at
                FROM draft_sessions AS sessions
                JOIN draft_insights AS insights ON insights.draft_id = sessions.draft_id
                WHERE
                    sessions.telegram_id = ?
                    AND sessions.draft_type = 'insight'
                    AND sessions.status = 'saved'
                ORDER BY sessions.updated_at DESC
                LIMIT 1
                """,
                (telegram_id,),
            ).fetchone()

            if row is None:
                return None

            draft_id = str(row["draft_id"])
            message_rows = self._message_rows(connection, draft_id)
            attachment_rows = self._attachment_rows(connection, draft_id)

        return _draft_from_row(row, message_rows, attachment_rows)

    def clear_draft(self, telegram_id: int) -> None:
        draft_id = self._get_dialog_draft_id(telegram_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM dialog_states WHERE telegram_id = ? AND flow = 'insight'", (telegram_id,))
            if draft_id is not None:
                connection.execute("DELETE FROM draft_sessions WHERE draft_id = ?", (draft_id,))

    def _get_dialog_draft_id(self, telegram_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT draft_id
                FROM dialog_states
                WHERE telegram_id = ? AND flow = 'insight'
                """,
                (telegram_id,),
            ).fetchone()
        if row is None or row["draft_id"] is None:
            return None
        return str(row["draft_id"])

    def _message_rows(self, connection: sqlite3.Connection, draft_id: str) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT text
            FROM draft_messages
            WHERE draft_id = ?
            ORDER BY message_order
            """,
            (draft_id,),
        ).fetchall()

    def _attachment_rows(self, connection: sqlite3.Connection, draft_id: str) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT local_file_path, transcription_text, duration_seconds
            FROM draft_attachments
            WHERE draft_id = ? AND transcription_status = 'success'
            ORDER BY draft_attachment_id
            """,
            (draft_id,),
        ).fetchall()

    def _touch(
        self,
        connection: sqlite3.Connection,
        draft_id: str,
        telegram_id: int,
        occurred_at: str,
    ) -> None:
        connection.execute(
            "UPDATE draft_sessions SET updated_at = ? WHERE draft_id = ?",
            (occurred_at, draft_id),
        )
        connection.execute(
            "UPDATE draft_insights SET updated_at = ? WHERE draft_id = ?",
            (occurred_at, draft_id),
        )
        connection.execute(
            "UPDATE dialog_states SET step = 'awaiting_text', updated_at = ? WHERE telegram_id = ?",
            (occurred_at, telegram_id),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _draft_from_row(
    row: sqlite3.Row,
    message_rows: list[sqlite3.Row],
    attachment_rows: list[sqlite3.Row],
) -> InsightDraft:
    return InsightDraft(
        draft_id=str(row["draft_id"]),
        telegram_id=int(row["telegram_id"]),
        participant_id=str(row["participant_id"]),
        goal_id=str(row["goal_id"]),
        week_number=int(row["week_number"]),
        insight_scope=str(row["insight_scope"]),
        insight_title=row["insight_title"],
        insight_text="\n".join(str(message["text"]) for message in message_rows),
        message_count=len(message_rows),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        saved_insight_id=row["saved_insight_id"],
        saved_at=row["saved_at"],
        expires_at=row["expires_at"],
        voice_attachments=tuple(
            InsightVoiceAttachment(
                local_file_path=str(attachment["local_file_path"]),
                transcription_text=str(attachment["transcription_text"] or ""),
                duration_seconds=int(attachment["duration_seconds"]),
            )
            for attachment in attachment_rows
        ),
    )
