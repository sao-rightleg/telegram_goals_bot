from pathlib import Path

import pytest

from app.config import ConfigurationError, load_settings, redact_mapping, redact_value
from app.logging import setup_logging


def complete_env() -> dict[str, str]:
    return {
        "MAIN_TELEGRAM_BOT_TOKEN": "main-token-123",
        "ERROR_TELEGRAM_BOT_TOKEN": "error-token-456",
        "NOTIFICATION_TELEGRAM_BOT_TOKEN": "notification-token-789",
        "GOOGLE_SHEETS_ID": "sheet-id",
        "GOOGLE_APPLICATION_CREDENTIALS": "credentials.json",
        "ADMIN_TELEGRAM_ID": "1001",
        "ADMIN_ERROR_CHAT_ID": "1002",
        "SITNIKOV_TELEGRAM_ID": "1003",
        "IVAN_LARKIN_TELEGRAM_ID": "1004",
        "MARIA_TELEGRAM_ID": "1005",
        "SQLITE_DB_PATH": "data/sqlite/bot.sqlite3",
        "AUDIO_STORAGE_DIR": "data/audio",
        "PDF_STORAGE_DIR": "reports/pdf",
        "LOG_LEVEL": "INFO",
    }


def test_settings_load_from_fake_env() -> None:
    settings = load_settings(environ=complete_env())

    assert settings.telegram.main_bot_token == "main-token-123"
    assert settings.google_sheets.sheet_id == "sheet-id"
    assert settings.storage.sqlite_db_path == Path("data/sqlite/bot.sqlite3")
    assert settings.runtime.log_level == "INFO"


def test_missing_required_setting_fails_clearly() -> None:
    env = complete_env()
    env.pop("GOOGLE_SHEETS_ID")

    with pytest.raises(ConfigurationError) as error:
        load_settings(environ=env)

    assert "GOOGLE_SHEETS_ID" in str(error.value)


@pytest.mark.parametrize(
    "missing_token",
    [
        "MAIN_TELEGRAM_BOT_TOKEN",
        "ERROR_TELEGRAM_BOT_TOKEN",
        "NOTIFICATION_TELEGRAM_BOT_TOKEN",
    ],
)
def test_strict_mode_requires_all_three_bot_tokens(missing_token: str) -> None:
    env = complete_env()
    env.pop(missing_token)

    with pytest.raises(ConfigurationError) as error:
        load_settings(environ=env, strict=True)

    assert missing_token in str(error.value)


def test_secret_values_are_redacted() -> None:
    settings = load_settings(environ=complete_env())

    redacted = redact_mapping(settings.as_dict())

    redacted_text = repr(redacted)
    assert "main-token-123" not in redacted_text
    assert "error-token-456" not in redacted_text
    assert "notification-token-789" not in redacted_text
    assert "credentials.json" not in redacted_text
    assert redact_value("plain-value") == "plain-value"
    assert redact_value("main-token-123") == "[REDACTED]"


def test_three_bot_tokens_are_distinct_settings() -> None:
    settings = load_settings(environ=complete_env())

    assert settings.telegram.main_bot_token != settings.telegram.error_bot_token
    assert settings.telegram.error_bot_token != settings.telegram.notification_bot_token


def test_env_file_loading_does_not_require_real_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in complete_env().items()),
        encoding="utf-8",
    )

    settings = load_settings(environ={}, env_file=env_file)

    assert settings.telegram.notification_bot_token == "notification-token-789"


def test_timezone_is_not_runtime_config() -> None:
    env = complete_env()
    env["APP_TIMEZONE"] = "Europe/Berlin"

    settings = load_settings(environ=env)

    assert "timezone" not in settings.runtime.as_dict()
    assert "APP_TIMEZONE" not in settings.as_dict()


def test_logging_setup_uses_redacted_metadata(caplog: pytest.LogCaptureFixture) -> None:
    settings = load_settings(environ=complete_env())
    logger = setup_logging(settings)

    with caplog.at_level("INFO"):
        logger.info("settings loaded", extra={"settings": redact_mapping(settings.as_dict())})

    log_output = caplog.text
    assert "settings loaded" in log_output
    assert "main-token-123" not in log_output
