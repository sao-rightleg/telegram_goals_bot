import sqlite3
from pathlib import Path

from app.storage.insight_drafts import InsightDraftRepository
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables


NOW = "2026-07-02T10:00:00+05:00"
LATER = "2026-07-02T10:05:00+05:00"


def test_create_insight_draft_writes_technical_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    repository.create_draft(
        draft_id="draft-1",
        telegram_id=1001,
        participant_id="P001",
        goal_id="G001",
        week_number=3,
        occurred_at=NOW,
    )

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.draft_id == "draft-1"
    assert draft.telegram_id == 1001
    assert draft.participant_id == "P001"
    assert draft.goal_id == "G001"
    assert draft.week_number == 3
    assert draft.insight_scope == "current_week"
    assert draft.insight_title is None
    assert draft.insight_text == ""
    assert draft.message_count == 0
    assert draft.saved_insight_id is None
    assert draft.saved_at is None


def test_append_text_messages_preserves_order(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_draft(repository)

    repository.append_text_message(1001, "Первое сообщение", occurred_at=NOW, telegram_message_id=501)
    repository.append_text_message(1001, "Второе сообщение", occurred_at=LATER, telegram_message_id=502)

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.insight_text == "Первое сообщение\nВторое сообщение"
    assert draft.message_count == 2
    assert draft.updated_at == LATER


def test_set_title_and_mark_saved_are_recoverable(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = InsightDraftRepository(db_path)
    _create_draft(repository)
    repository.append_text_message(1001, "Текст инсайта", occurred_at=NOW)
    repository.set_title(1001, "Короткий заголовок", occurred_at=LATER)

    repository.mark_saved(1001, saved_insight_id="I001", saved_at=LATER)

    assert repository.get_active_draft(1001) is None
    saved = repository.get_recent_saved_draft(1001)
    assert saved is not None
    assert saved.draft_id == "draft-1"
    assert saved.insight_title == "Короткий заголовок"
    assert saved.insight_text == ""
    assert saved.message_count == 0
    assert saved.saved_insight_id == "I001"
    assert saved.saved_at == LATER
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM draft_messages").fetchone()[0] == 0


def test_clear_draft_removes_active_state(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = InsightDraftRepository(db_path)
    _create_draft(repository)
    repository.append_text_message(1001, "Текст", occurred_at=NOW)

    repository.clear_draft(1001)

    assert repository.get_active_draft(1001) is None
    assert repository.get_recent_saved_draft(1001) is None
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM dialog_states").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_insights").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_messages").fetchone()[0] == 0


def test_repository_does_not_create_business_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = InsightDraftRepository(db_path)

    _create_draft(repository)
    repository.append_text_message(1001, "Текст", occurred_at=NOW)
    repository.set_title(1001, "Заголовок", occurred_at=LATER)

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_missing_or_invalid_draft_returns_none_or_recoverable_error(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = InsightDraftRepository(db_path)

    assert repository.get_active_draft(1001) is None

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO dialog_states (
                telegram_id, participant_id, role, flow, step, draft_id, started_at, updated_at
            )
            VALUES (
                1001, 'P001', 'participant', 'insight', 'awaiting_text',
                'missing-draft', ?, ?
            )
            """,
            (NOW, NOW),
        )

    assert repository.get_active_draft(1001) is None
    repository.clear_draft(1001)
    assert repository.get_active_draft(1001) is None


def _repository(tmp_path: Path) -> InsightDraftRepository:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    return InsightDraftRepository(db_path)


def _create_draft(repository: InsightDraftRepository) -> None:
    repository.create_draft(
        draft_id="draft-1",
        telegram_id=1001,
        participant_id="P001",
        goal_id="G001",
        week_number=3,
        occurred_at=NOW,
    )
