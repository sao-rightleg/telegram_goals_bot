from pathlib import Path

from app.storage.paths import (
    AUDIO_RETENTION_DAYS,
    PDF_RETENTION_DAYS_AFTER_CHALLENGE,
    SQLITE_BACKUP_RETENTION_DAYS,
    StoragePathPolicy,
)


def assert_local_path(path: Path) -> None:
    as_text = str(path)
    assert "://" not in as_text
    assert not as_text.startswith("http:")
    assert not as_text.startswith("https:")


def test_audio_path_policy() -> None:
    policy = StoragePathPolicy()

    path = policy.audio_path(
        year=2026,
        week_number=1,
        team_slug="male_team",
        participant_id="participant_001",
        file_name="report_001.ogg",
    )

    assert path == Path("data/audio/2026/week_01/male_team/participant_001/report_001.ogg")
    assert AUDIO_RETENTION_DAYS == 30
    assert_local_path(path)


def test_sqlite_path_policy() -> None:
    policy = StoragePathPolicy()

    path = policy.sqlite_db_path()

    assert path == Path("data/sqlite/bot.sqlite3")
    assert_local_path(path)


def test_pdf_path_policy() -> None:
    policy = StoragePathPolicy()

    path = policy.pdf_path(year=2026, week_number=3, team_slug="male_team", file_name="team.pdf")

    assert path == Path("reports/pdf/2026/week_03/male_team/team.pdf")
    assert PDF_RETENTION_DAYS_AFTER_CHALLENGE == 183
    assert_local_path(path)


def test_backup_paths_are_under_backups() -> None:
    policy = StoragePathPolicy()

    sqlite_backup = policy.sqlite_backup_path(file_name="state.sqlite3")
    sheets_backup = policy.google_sheets_export_path(file_name="export.xlsx")
    pdf_backup = policy.pdf_backup_path(file_name="team.pdf")

    assert sqlite_backup == Path("backups/sqlite/state.sqlite3")
    assert sheets_backup == Path("backups/google_sheets_exports/export.xlsx")
    assert pdf_backup == Path("backups/pdf/team.pdf")
    assert SQLITE_BACKUP_RETENTION_DAYS == 14
    for path in (sqlite_backup, sheets_backup, pdf_backup):
        assert path.parts[0] == "backups"
        assert_local_path(path)
