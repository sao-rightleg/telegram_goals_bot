import sqlite3
from pathlib import Path

from app.services.weekly_report_models import WeeklyReportStatus
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = "2026-07-02T10:00:00+05:00"
LATER = "2026-07-02T10:05:00+05:00"


def test_create_weekly_report_draft_writes_technical_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    repository.create_draft(
        draft_id="draft-1",
        telegram_id=1001,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=2,
        occurred_at=NOW,
    )

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.draft_id == "draft-1"
    assert draft.participant_id == "P001"
    assert draft.team_id == "T001"
    assert draft.goal_id == "G001"
    assert draft.week_number == 2
    assert draft.status_code is None
    assert draft.status_symbol is None
    assert draft.selected_step_ids == ()
    assert draft.report_text == ""


def test_append_text_messages_preserves_order(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_draft(repository)

    repository.append_text_message(1001, "Первое сообщение", occurred_at=NOW, telegram_message_id=501)
    repository.append_text_message(1001, "Второе сообщение", occurred_at=LATER, telegram_message_id=502)

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.report_text == "Первое сообщение\nВторое сообщение"
    assert draft.message_count == 2


def test_update_status_and_selected_steps(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_draft(repository)

    repository.update_status_and_steps(
        1001,
        WeeklyReportStatus.GREEN,
        ["S003", "S001", "S003"],
        occurred_at=LATER,
    )

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.status_code == "green"
    assert draft.status_symbol == "🟩"
    assert draft.selected_step_ids == ("S001", "S003")
    assert draft.updated_at == LATER


def test_clear_draft_removes_technical_state(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)
    _create_draft(repository)
    repository.append_text_message(1001, "Текст", occurred_at=NOW)

    repository.clear_draft(1001)

    assert repository.get_active_draft(1001) is None
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM dialog_states").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_reports").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM draft_messages").fetchone()[0] == 0


def test_repository_does_not_create_business_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)

    _create_draft(repository)
    repository.append_text_message(1001, "Текст", occurred_at=NOW)

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_missing_or_invalid_draft_returns_none_or_recoverable_error(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)

    assert repository.get_active_draft(1001) is None

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO dialog_states (
                telegram_id, participant_id, role, flow, step, draft_id, started_at, updated_at
            )
            VALUES (
                1001, 'P001', 'participant', 'weekly_report', 'awaiting_text',
                'missing-draft', ?, ?
            )
            """,
            (NOW, NOW),
        )

    assert repository.get_active_draft(1001) is None
    repository.clear_draft(1001)
    assert repository.get_active_draft(1001) is None


def _repository(tmp_path: Path) -> WeeklyReportDraftRepository:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    return WeeklyReportDraftRepository(db_path)


def _create_draft(repository: WeeklyReportDraftRepository) -> None:
    repository.create_draft(
        draft_id="draft-1",
        telegram_id=1001,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=2,
        occurred_at=NOW,
    )
