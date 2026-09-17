from pathlib import Path

import pytest

from app.config import ConfigurationError, load_settings


def _env(tmp_path: Path) -> dict[str, str]:
    return {
        "MAIN_TELEGRAM_BOT_TOKEN": "main-token",
        "ERROR_TELEGRAM_BOT_TOKEN": "error-token",
        "NOTIFICATION_TELEGRAM_BOT_TOKEN": "notification-token",
        "GOOGLE_SHEETS_ID": "sheet",
        "CHALLENGE_FLOWS_SHEETS_ID": "registry",
        "GOOGLE_APPLICATION_CREDENTIALS": str(tmp_path / "credentials.json"),
        "ADMIN_TELEGRAM_ID": "1",
        "ADMIN_ERROR_CHAT_ID": "2",
        "SITNIKOV_TELEGRAM_ID": "3",
        "SQLITE_DB_PATH": str(tmp_path / "state.sqlite3"),
        "AUDIO_STORAGE_DIR": str(tmp_path / "audio"),
        "PDF_STORAGE_DIR": str(tmp_path / "pdf"),
        "TRANSCRIPTION_PROVIDER": "fake",
    }


def test_rupor_config_is_disabled_when_both_values_are_absent(tmp_path: Path) -> None:
    settings = load_settings(environ=_env(tmp_path), env_file=None, strict=True)

    assert settings.rupor.bot_token is None
    assert settings.rupor.allowed_telegram_ids == ()


def test_rupor_config_requires_exactly_three_unique_positive_ids(tmp_path: Path) -> None:
    env = {
        **_env(tmp_path),
        "RUPOR_TELEGRAM_BOT_TOKEN": "rupor-token",
        "RUPOR_ALLOWED_TELEGRAM_IDS": "101,102,103",
    }

    settings = load_settings(environ=env, env_file=None, strict=True)

    assert settings.rupor.bot_token == "rupor-token"
    assert settings.rupor.allowed_telegram_ids == (101, 102, 103)


@pytest.mark.parametrize("ids", ["101,102", "101,101,103", "101,-2,103", "101,nope,103"])
def test_rupor_config_rejects_invalid_operator_list(tmp_path: Path, ids: str) -> None:
    env = {
        **_env(tmp_path),
        "RUPOR_TELEGRAM_BOT_TOKEN": "rupor-token",
        "RUPOR_ALLOWED_TELEGRAM_IDS": ids,
    }

    with pytest.raises(ConfigurationError, match="RUPOR_ALLOWED_TELEGRAM_IDS"):
        load_settings(environ=env, env_file=None, strict=True)


def test_rupor_config_rejects_half_configured_bot(tmp_path: Path) -> None:
    env = {**_env(tmp_path), "RUPOR_TELEGRAM_BOT_TOKEN": "rupor-token"}

    with pytest.raises(ConfigurationError, match="configured together"):
        load_settings(environ=env, env_file=None, strict=True)
