"""Local file-storage path policy for the MVP foundation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


AUDIO_RETENTION_DAYS = 30
SQLITE_BACKUP_RETENTION_DAYS = 14
GOOGLE_SHEETS_EXPORT_RETENTION_DAYS = 14
PDF_RETENTION_DAYS_AFTER_CHALLENGE = 183


@dataclass(frozen=True)
class StoragePathPolicy:
    audio_root: Path = Path("data/audio")
    sqlite_root: Path = Path("data/sqlite")
    pdf_root: Path = Path("reports/pdf")
    backups_root: Path = Path("backups")
    sqlite_file_name: str = "bot.sqlite3"

    def sqlite_db_path(self) -> Path:
        return self.sqlite_root / self.sqlite_file_name

    def audio_path(
        self,
        *,
        year: int,
        week_number: int,
        team_slug: str,
        participant_id: str,
        file_name: str,
    ) -> Path:
        return (
            self.audio_root
            / str(year)
            / _week_dir(week_number)
            / _safe_fragment(team_slug)
            / _safe_fragment(participant_id)
            / _safe_fragment(file_name)
        )

    def pdf_path(self, *, year: int, week_number: int, team_slug: str, file_name: str) -> Path:
        return (
            self.pdf_root
            / str(year)
            / _week_dir(week_number)
            / _safe_fragment(team_slug)
            / _safe_fragment(file_name)
        )

    def sqlite_backup_path(self, *, file_name: str) -> Path:
        return self.backups_root / "sqlite" / _safe_fragment(file_name)

    def google_sheets_export_path(self, *, file_name: str) -> Path:
        return self.backups_root / "google_sheets_exports" / _safe_fragment(file_name)

    def pdf_backup_path(self, *, file_name: str) -> Path:
        return self.backups_root / "pdf" / _safe_fragment(file_name)


def _week_dir(week_number: int) -> str:
    if week_number < 1:
        raise ValueError("week_number must be positive")
    return f"week_{week_number:02d}"


def _safe_fragment(value: str) -> str:
    if not value or "://" in value:
        raise ValueError("path fragment must be local and non-empty")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
        raise ValueError("path fragment must not contain path traversal")
    return value
