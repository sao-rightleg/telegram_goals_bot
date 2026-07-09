from pathlib import Path

import pytest

from app.config import load_settings
from app.runtime import RuntimeNotImplementedError, initialize_runtime, main, run_bot
from app.storage.sqlite import REQUIRED_TECHNICAL_TABLES, list_tables


def runtime_env(tmp_path: Path) -> dict[str, str]:
    return {
        "MAIN_TELEGRAM_BOT_TOKEN": "main-token-123",
        "ERROR_TELEGRAM_BOT_TOKEN": "error-token-456",
        "NOTIFICATION_TELEGRAM_BOT_TOKEN": "notification-token-789",
        "GOOGLE_SHEETS_ID": "sheet-id",
        "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "credentials.json"),
        "ADMIN_TELEGRAM_ID": "1001",
        "ADMIN_ERROR_CHAT_ID": "1002",
        "SITNIKOV_TELEGRAM_ID": "1003",
        "SQLITE_DB_PATH": str(tmp_path / "data" / "sqlite" / "bot.sqlite3"),
        "AUDIO_STORAGE_DIR": str(tmp_path / "data" / "audio"),
        "PDF_STORAGE_DIR": str(tmp_path / "reports" / "pdf"),
        "LOG_LEVEL": "INFO",
    }


def test_initialize_runtime_creates_storage_dirs_and_sqlite_schema(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))

    result = initialize_runtime(settings)

    assert settings.storage.audio_storage_dir.is_dir()
    assert settings.storage.pdf_storage_dir.is_dir()
    assert settings.storage.sqlite_db_path.exists()
    assert REQUIRED_TECHNICAL_TABLES.issubset(list_tables(settings.storage.sqlite_db_path))
    assert result.sqlite_db_path == settings.storage.sqlite_db_path
    assert result.created_storage_dirs == (
        settings.storage.sqlite_db_path.parent,
        settings.storage.audio_storage_dir,
        settings.storage.pdf_storage_dir,
    )


def test_run_bot_fails_clearly_until_live_runtime_exists(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))

    with pytest.raises(RuntimeNotImplementedError) as error:
        run_bot(settings)

    assert "live Telegram polling runtime is not implemented" in str(error.value)


def test_cli_check_config_uses_env_file_and_initializes_storage(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in runtime_env(tmp_path).items()),
        encoding="utf-8",
    )

    exit_code = main(["--env-file", str(env_file), "check-config"])

    assert exit_code == 0
    assert (tmp_path / "data" / "sqlite" / "bot.sqlite3").exists()
