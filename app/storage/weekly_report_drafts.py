"""Repository for SQLite weekly report draft state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from app.services.weekly_report_models import WeeklyReportStatus


_UNSELECTED_STATUS_CODE = "gray"
_UNSELECTED_STATUS_SYMBOL = "⬜"


@dataclass(frozen=True)
class WeeklyReportVoiceAttachment:
    local_file_path: str
    transcription_text: str
    duration_seconds: int


@dataclass(frozen=True)
class WeeklyReportDraft:
    draft_id: str
    telegram_id: int
    participant_id: str
    team_id: str
    goal_id: str
    week_number: int
    status_code: str | None
    status_symbol: str | None
    selected_step_ids: tuple[str, ...]
    report_text: str
    message_count: int
    created_at: str
    updated_at: str
    expires_at: str | None = None
    voice_attachments: tuple[WeeklyReportVoiceAttachment, ...] = ()
    flow_source: str = "participant_bot"
    submitted_by_id: str | None = None
    submitted_by_role: str = "participant"
    selected_participant_id: str | None = None


class WeeklyReportDraftRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def create_draft(
        self,
        *,
        draft_id: str,
        telegram_id: int,
        participant_id: str,
        team_id: str,
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
                VALUES (?, 'weekly_report', ?, ?, 'participant_bot', 'active', ?, ?, ?)
                """,
                (draft_id, participant_id, telegram_id, occurred_at, occurred_at, expires_at),
            )
            connection.execute(
                """
                INSERT INTO draft_reports (
                    draft_id,
                    participant_id,
                    team_id,
                    goal_id,
                    week_number,
                    flow_source,
                    status_code,
                    status_symbol,
                    submitted_by_id,
                    submitted_by_role,
                    selected_step_ids,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'participant_bot', ?, ?, ?, 'participant', NULL, ?, ?)
                """,
                (
                    draft_id,
                    participant_id,
                    team_id,
                    goal_id,
                    week_number,
                    _UNSELECTED_STATUS_CODE,
                    _UNSELECTED_STATUS_SYMBOL,
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
                    selected_status,
                    selected_step_ids,
                    draft_id,
                    started_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, 'participant', 'weekly_report', 'draft_started', ?, NULL, NULL, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    participant_id = excluded.participant_id,
                    role = excluded.role,
                    flow = excluded.flow,
                    step = excluded.step,
                    week_number = excluded.week_number,
                    selected_status = excluded.selected_status,
                    selected_step_ids = excluded.selected_step_ids,
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

    def create_captain_manual_draft(
        self,
        *,
        draft_id: str,
        telegram_id: int,
        captain_participant_id: str,
        target_participant_id: str,
        team_id: str,
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
                VALUES (?, 'captain_manual_report', ?, ?, 'captain_manual', 'active', ?, ?, ?)
                """,
                (draft_id, target_participant_id, telegram_id, occurred_at, occurred_at, expires_at),
            )
            connection.execute(
                """
                INSERT INTO draft_reports (
                    draft_id,
                    participant_id,
                    team_id,
                    goal_id,
                    week_number,
                    flow_source,
                    status_code,
                    status_symbol,
                    submitted_by_id,
                    submitted_by_role,
                    selected_step_ids,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'captain_manual', ?, ?, ?, 'captain', NULL, ?, ?)
                """,
                (
                    draft_id,
                    target_participant_id,
                    team_id,
                    goal_id,
                    week_number,
                    _UNSELECTED_STATUS_CODE,
                    _UNSELECTED_STATUS_SYMBOL,
                    captain_participant_id,
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
                    selected_status,
                    selected_participant_id,
                    selected_step_ids,
                    draft_id,
                    started_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, 'captain', 'captain_manual_report', 'draft_started', ?, NULL, ?, NULL, ?, ?, ?, ?)
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
                    telegram_id,
                    captain_participant_id,
                    week_number,
                    target_participant_id,
                    draft_id,
                    occurred_at,
                    occurred_at,
                    expires_at,
                ),
            )

    def update_status_and_steps(
        self,
        telegram_id: int,
        status: WeeklyReportStatus,
        selected_step_ids: list[str] | tuple[str, ...],
        *,
        occurred_at: str,
    ) -> None:
        draft_id = self._get_dialog_draft_id(telegram_id)
        if draft_id is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={telegram_id}")

        serialized_step_ids = _serialize_step_ids(selected_step_ids)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE draft_reports
                SET
                    status_code = ?,
                    status_symbol = ?,
                    selected_step_ids = ?,
                    updated_at = ?
                WHERE draft_id = ?
                """,
                (status.code, status.symbol, serialized_step_ids or None, occurred_at, draft_id),
            )
            connection.execute(
                """
                UPDATE dialog_states
                SET
                    step = 'awaiting_text',
                    selected_status = ?,
                    selected_step_ids = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (status.code, serialized_step_ids or None, occurred_at, telegram_id),
            )

    def preselect_steps(
        self,
        telegram_id: int,
        selected_step_ids: list[str] | tuple[str, ...],
        *,
        occurred_at: str,
    ) -> None:
        draft_id = self._get_dialog_draft_id(telegram_id)
        if draft_id is None:
            raise KeyError(f"Active weekly report draft not found for telegram_id={telegram_id}")

        serialized_step_ids = _serialize_step_ids(selected_step_ids)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE draft_reports
                SET selected_step_ids = ?, updated_at = ?
                WHERE draft_id = ?
                """,
                (serialized_step_ids or None, occurred_at, draft_id),
            )
            connection.execute(
                """
                UPDATE dialog_states
                SET
                    step = 'step_preselected',
                    selected_step_ids = ?,
                    updated_at = ?
                WHERE telegram_id = ?
                """,
                (serialized_step_ids or None, occurred_at, telegram_id),
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
            raise KeyError(f"Active weekly report draft not found for telegram_id={telegram_id}")

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
            connection.execute(
                "UPDATE draft_sessions SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE draft_reports SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE dialog_states SET updated_at = ? WHERE telegram_id = ?",
                (occurred_at, telegram_id),
            )

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
            raise KeyError(f"Active weekly report draft not found for telegram_id={telegram_id}")

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
            connection.execute(
                "UPDATE draft_sessions SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE draft_reports SET updated_at = ? WHERE draft_id = ?",
                (occurred_at, draft.draft_id),
            )
            connection.execute(
                "UPDATE dialog_states SET updated_at = ? WHERE telegram_id = ?",
                (occurred_at, telegram_id),
            )

    def get_active_draft(self, telegram_id: int) -> WeeklyReportDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sessions.draft_id,
                    sessions.telegram_id,
                    sessions.participant_id,
                    reports.team_id,
                    reports.goal_id,
                    reports.week_number,
                    reports.status_code,
                    reports.status_symbol,
                    reports.selected_step_ids,
                    reports.flow_source,
                    reports.submitted_by_id,
                    reports.submitted_by_role,
                    dialog.selected_participant_id,
                    sessions.created_at,
                    reports.updated_at,
                    sessions.expires_at
                FROM dialog_states AS dialog
                JOIN draft_sessions AS sessions ON sessions.draft_id = dialog.draft_id
                JOIN draft_reports AS reports ON reports.draft_id = sessions.draft_id
                WHERE
                    dialog.telegram_id = ?
                    AND dialog.flow IN ('weekly_report', 'captain_manual_report')
                    AND sessions.draft_type IN ('weekly_report', 'captain_manual_report')
                    AND sessions.status = 'active'
                """,
                (telegram_id,),
            ).fetchone()

            if row is None:
                return None

            message_rows = connection.execute(
                """
                SELECT text
                FROM draft_messages
                WHERE draft_id = ?
                ORDER BY message_order
                """,
                (row["draft_id"],),
            ).fetchall()
            attachment_rows = connection.execute(
                """
                SELECT local_file_path, transcription_text, duration_seconds
                FROM draft_attachments
                WHERE draft_id = ? AND transcription_status = 'success'
                ORDER BY draft_attachment_id
                """,
                (row["draft_id"],),
            ).fetchall()

        status_code = str(row["status_code"])
        status_symbol = str(row["status_symbol"])
        if status_code == _UNSELECTED_STATUS_CODE:
            status_code = None
            status_symbol = None

        return WeeklyReportDraft(
            draft_id=str(row["draft_id"]),
            telegram_id=int(row["telegram_id"]),
            participant_id=str(row["participant_id"]),
            team_id=str(row["team_id"]),
            goal_id=str(row["goal_id"]),
            week_number=int(row["week_number"]),
            status_code=status_code,
            status_symbol=status_symbol,
            selected_step_ids=_parse_step_ids(row["selected_step_ids"]),
            report_text="\n".join(str(message["text"]) for message in message_rows),
            message_count=len(message_rows),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            expires_at=row["expires_at"],
            voice_attachments=tuple(
                WeeklyReportVoiceAttachment(
                    local_file_path=str(attachment["local_file_path"]),
                    transcription_text=str(attachment["transcription_text"] or ""),
                    duration_seconds=int(attachment["duration_seconds"]),
                )
                for attachment in attachment_rows
            ),
            flow_source=str(row["flow_source"]),
            submitted_by_id=str(row["submitted_by_id"]),
            submitted_by_role=str(row["submitted_by_role"]),
            selected_participant_id=row["selected_participant_id"],
        )

    def clear_draft(self, telegram_id: int) -> None:
        draft_id = self._get_dialog_draft_id(telegram_id)
        with self._connect() as connection:
            connection.execute("DELETE FROM dialog_states WHERE telegram_id = ?", (telegram_id,))
            if draft_id is not None:
                connection.execute("DELETE FROM draft_sessions WHERE draft_id = ?", (draft_id,))

    def _get_dialog_draft_id(self, telegram_id: int) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT draft_id
                FROM dialog_states
                WHERE telegram_id = ? AND flow IN ('weekly_report', 'captain_manual_report')
                """,
                (telegram_id,),
            ).fetchone()
        if row is None or row["draft_id"] is None:
            return None
        return str(row["draft_id"])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _serialize_step_ids(step_ids: list[str] | tuple[str, ...]) -> str:
    return ",".join(sorted(set(step_ids)))


def _parse_step_ids(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    return tuple(part for part in str(value).split(",") if part)
