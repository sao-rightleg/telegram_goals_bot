"""SQLite repository for unfinished participant self-registration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class RegistrationDraft:
    telegram_id: int
    flow_id: str
    created_at: str
    updated_at: str
    expires_at: str
    status: str = "active"
    claim_token: str | None = None
    consent_given_at: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    captain_id: str | None = None


class RegistrationDraftRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def get(self, telegram_id: int) -> RegistrationDraft | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM registration_drafts WHERE telegram_id = ?",
                (telegram_id,),
            ).fetchone()
        return RegistrationDraft(**dict(row)) if row is not None else None

    def save(self, draft: RegistrationDraft) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO registration_drafts (
                    telegram_id, flow_id, status, claim_token, consent_given_at,
                    first_name, last_name, captain_id, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    flow_id = excluded.flow_id,
                    status = excluded.status,
                    claim_token = excluded.claim_token,
                    consent_given_at = excluded.consent_given_at,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    captain_id = excluded.captain_id,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    draft.telegram_id, draft.flow_id, draft.status, draft.claim_token,
                    draft.consent_given_at, draft.first_name, draft.last_name,
                    draft.captain_id, draft.created_at, draft.updated_at, draft.expires_at,
                ),
            )

    def claim_finalization(
        self, telegram_id: int, *, claim_token: str, updated_at: str, stale_before: str
    ) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE registration_drafts
                SET status = 'finalizing', claim_token = ?, updated_at = ?
                WHERE telegram_id = ?
                  AND (status = 'active' OR (status = 'finalizing' AND updated_at <= ?))
                """,
                (claim_token, updated_at, telegram_id, stale_before),
            )
        return cursor.rowcount == 1

    def release_finalization(self, telegram_id: int, *, claim_token: str, updated_at: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE registration_drafts
                SET status = 'active', claim_token = NULL, updated_at = ?
                WHERE telegram_id = ? AND status = 'finalizing' AND claim_token = ?
                """,
                (updated_at, telegram_id, claim_token),
            )

    def update(self, telegram_id: int, *, updated_at: str, **changes: str | None) -> RegistrationDraft:
        draft = self.get(telegram_id)
        if draft is None:
            raise KeyError(f"Registration draft not found: {telegram_id}")
        updated = replace(draft, updated_at=updated_at, **changes)
        self.save(updated)
        return updated

    def clear(self, telegram_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM registration_drafts WHERE telegram_id = ?", (telegram_id,))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection
