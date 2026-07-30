import sqlite3
from pathlib import Path

from app.services.weekly_report_models import WeeklyReportStatus
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = "2026-07-02T10:00:00+05:00"
LATER = "2026-07-02T10:05:00+05:00"
LATEST = "2026-07-02T10:10:00+05:00"


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
    assert draft.flow_source == "participant_bot"
    assert draft.submitted_by_id == "P001"
    assert draft.submitted_by_role == "participant"
    assert draft.selected_participant_id is None


def test_create_weekly_report_draft_replaces_stale_same_id_session(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO draft_sessions (
                draft_id, draft_type, participant_id, telegram_id, flow_source, status,
                created_at, updated_at
            )
            VALUES ('draft-1', 'weekly_report', 'P001', 1001, 'participant_bot', 'active', ?, ?)
            """,
            (NOW, NOW),
        )

    repository.create_draft(
        draft_id="draft-1",
        telegram_id=1001,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=2,
        occurred_at=LATER,
    )

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.draft_id == "draft-1"
    assert draft.created_at == LATER


def test_create_captain_manual_report_draft_writes_selected_participant_state(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)

    repository.create_captain_manual_draft(
        draft_id="captain-draft-1",
        telegram_id=2001,
        captain_participant_id="C001",
        target_participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=4,
        occurred_at=NOW,
    )

    draft = repository.get_active_draft(2001)
    assert draft is not None
    assert draft.draft_id == "captain-draft-1"
    assert draft.telegram_id == 2001
    assert draft.participant_id == "P001"
    assert draft.selected_participant_id == "P001"
    assert draft.team_id == "T001"
    assert draft.goal_id == "G001"
    assert draft.week_number == 4
    assert draft.flow_source == "captain_manual"
    assert draft.submitted_by_id == "C001"
    assert draft.submitted_by_role == "captain"

    with sqlite3.connect(db_path) as connection:
        session = connection.execute(
            "SELECT draft_type, participant_id, telegram_id, flow_source FROM draft_sessions"
        ).fetchone()
        report = connection.execute(
            "SELECT participant_id, submitted_by_id, submitted_by_role, flow_source FROM draft_reports"
        ).fetchone()
        dialog = connection.execute(
            "SELECT participant_id, role, flow, selected_participant_id, draft_id FROM dialog_states"
        ).fetchone()

    assert session == ("captain_manual_report", "P001", 2001, "captain_manual")
    assert report == ("P001", "C001", "captain", "captain_manual")
    assert dialog == ("C001", "captain", "captain_manual_report", "P001", "captain-draft-1")


def test_append_text_messages_preserves_order(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_draft(repository)

    repository.append_text_message(1001, "Первое сообщение", occurred_at=NOW, telegram_message_id=501)
    repository.append_text_message(1001, "Второе сообщение", occurred_at=LATER, telegram_message_id=502)

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.report_text == "Первое сообщение\nВторое сообщение"
    assert draft.message_count == 2


def test_append_voice_transcription_preserves_order(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_draft(repository)

    repository.append_text_message(1001, "Первое сообщение", occurred_at=NOW, telegram_message_id=501)
    repository.append_voice_transcription(
        1001,
        telegram_file_id="voice-file-1",
        local_file_path="data/audio/P001/week-2/voice-file-1.ogg",
        duration_seconds=42,
        transcription_text="Голосовой фрагмент",
        occurred_at=LATER,
        telegram_message_id=502,
    )
    repository.append_text_message(1001, "Третье сообщение", occurred_at=LATEST, telegram_message_id=503)

    draft = repository.get_active_draft(1001)

    assert draft is not None
    assert draft.report_text == "Первое сообщение\nГолосовой фрагмент\nТретье сообщение"
    assert draft.message_count == 3


def test_append_voice_attachment_stores_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)
    _create_draft(repository)

    repository.append_voice_transcription(
        1001,
        telegram_file_id="voice-file-1",
        local_file_path="data/audio/P001/week-2/voice-file-1.ogg",
        duration_seconds=42,
        transcription_text="Голосовой фрагмент",
        occurred_at=LATER,
        telegram_message_id=502,
    )

    with sqlite3.connect(db_path) as connection:
        attachment = connection.execute(
            """
            SELECT
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
            FROM draft_attachments
            """
        ).fetchone()
        message = connection.execute(
            "SELECT message_order, message_type, text, telegram_message_id FROM draft_messages"
        ).fetchone()

    assert attachment == (
        "draft-1",
        "P001",
        "voice-file-1",
        "data/audio/P001/week-2/voice-file-1.ogg",
        42,
        "success",
        "Голосовой фрагмент",
        None,
        LATER,
        LATER,
    )
    assert message == (1, "voice_transcription", "Голосовой фрагмент", 502)


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


def test_captain_manual_report_draft_clears_like_weekly_report_draft(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = WeeklyReportDraftRepository(db_path)
    repository.create_captain_manual_draft(
        draft_id="captain-draft-1",
        telegram_id=2001,
        captain_participant_id="C001",
        target_participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=4,
        occurred_at=NOW,
    )
    repository.append_text_message(2001, "Текст капитана", occurred_at=NOW)

    repository.clear_draft(2001)

    assert repository.get_active_draft(2001) is None
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
