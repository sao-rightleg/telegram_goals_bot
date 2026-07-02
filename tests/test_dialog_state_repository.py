import sqlite3
from pathlib import Path

import pytest

from app.storage.dialog_state import DialogState, DialogStateRepository
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables


def test_upsert_and_get_dialog_state(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = DialogStateRepository(db_path)

    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="participant",
            flow="consent",
            step="awaiting_consent",
            started_at="2026-07-02T10:00:00+05:00",
            updated_at="2026-07-02T10:00:00+05:00",
        )
    )

    assert repository.get(1001) == DialogState(
        telegram_id=1001,
        participant_id="P001",
        role="participant",
        flow="consent",
        step="awaiting_consent",
        started_at="2026-07-02T10:00:00+05:00",
        updated_at="2026-07-02T10:00:00+05:00",
    )


def test_upsert_replaces_state_for_same_telegram_id(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = DialogStateRepository(db_path)

    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="participant",
            flow="consent",
            step="awaiting_consent",
            started_at="2026-07-02T10:00:00+05:00",
            updated_at="2026-07-02T10:00:00+05:00",
        )
    )
    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="participant",
            flow="idle",
            step="menu",
            started_at="2026-07-02T10:00:00+05:00",
            updated_at="2026-07-02T10:05:00+05:00",
        )
    )

    assert repository.get(1001).flow == "idle"
    with sqlite3.connect(db_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM dialog_states").fetchone()[0]
    assert count == 1


def test_clear_dialog_state_removes_row(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = DialogStateRepository(db_path)

    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="participant",
            flow="idle",
            step="menu",
            started_at="2026-07-02T10:00:00+05:00",
            updated_at="2026-07-02T10:00:00+05:00",
        )
    )
    repository.clear(1001)

    assert repository.get(1001) is None


def test_repository_uses_existing_schema_only(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = DialogStateRepository(db_path)

    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="captain",
            flow="view_progress",
            step="render",
            started_at="2026-07-02T10:00:00+05:00",
            updated_at="2026-07-02T10:00:00+05:00",
        )
    )

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_invalid_flow_fails_clearly(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = DialogStateRepository(db_path)

    with pytest.raises(sqlite3.IntegrityError):
        repository.upsert(
            DialogState(
                telegram_id=1001,
                participant_id="P001",
                role="participant",
                flow="business_goal_cache",
                step="invalid",
                started_at="2026-07-02T10:00:00+05:00",
                updated_at="2026-07-02T10:00:00+05:00",
            )
        )
