"""Application settings loading and secret redaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
from typing import Mapping

from app.scheduler.calendar import DEFAULT_CHALLENGE_START_DATE


class ConfigurationError(ValueError):
    """Raised when required runtime configuration is missing or invalid."""


SECRET_KEY_PARTS = ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY", "KEY_PATH")
SECRET_VALUE_PARTS = ("token", "secret", "password", "credential", "api_key")
REDACTED = "[REDACTED]"


@dataclass(frozen=True)
class TelegramSettings:
    main_bot_token: str | None
    error_bot_token: str | None
    notification_bot_token: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "MAIN_TELEGRAM_BOT_TOKEN": self.main_bot_token,
            "ERROR_TELEGRAM_BOT_TOKEN": self.error_bot_token,
            "NOTIFICATION_TELEGRAM_BOT_TOKEN": self.notification_bot_token,
        }


@dataclass(frozen=True)
class TelegramRuntimeSettings:
    poll_timeout_seconds: int = 20
    poll_limit: int = 100
    request_timeout_seconds: int = 30

    def as_dict(self) -> dict[str, int]:
        return {
            "TELEGRAM_POLL_TIMEOUT_SECONDS": self.poll_timeout_seconds,
            "TELEGRAM_POLL_LIMIT": self.poll_limit,
            "TELEGRAM_REQUEST_TIMEOUT_SECONDS": self.request_timeout_seconds,
        }


@dataclass(frozen=True)
class GoogleSheetsSettings:
    sheet_id: str
    challenge_flows_sheet_id: str
    application_credentials: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "GOOGLE_SHEETS_ID": self.sheet_id,
            "CHALLENGE_FLOWS_SHEETS_ID": self.challenge_flows_sheet_id,
            "GOOGLE_APPLICATION_CREDENTIALS": str(self.application_credentials),
        }


@dataclass(frozen=True)
class AdminSettings:
    admin_telegram_id: int
    admin_error_chat_id: int
    sitnikov_telegram_id: int
    ivan_larkin_telegram_id: int | None = None
    maria_telegram_id: int | None = None

    def as_dict(self) -> dict[str, int | None]:
        return {
            "ADMIN_TELEGRAM_ID": self.admin_telegram_id,
            "ADMIN_ERROR_CHAT_ID": self.admin_error_chat_id,
            "SITNIKOV_TELEGRAM_ID": self.sitnikov_telegram_id,
            "IVAN_LARKIN_TELEGRAM_ID": self.ivan_larkin_telegram_id,
            "MARIA_TELEGRAM_ID": self.maria_telegram_id,
        }


@dataclass(frozen=True)
class StorageSettings:
    sqlite_db_path: Path
    audio_storage_dir: Path
    pdf_storage_dir: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "SQLITE_DB_PATH": str(self.sqlite_db_path),
            "AUDIO_STORAGE_DIR": str(self.audio_storage_dir),
            "PDF_STORAGE_DIR": str(self.pdf_storage_dir),
        }


@dataclass(frozen=True)
class RuntimeSettings:
    log_level: str = "INFO"

    def as_dict(self) -> dict[str, str]:
        return {"LOG_LEVEL": self.log_level}


@dataclass(frozen=True)
class ChallengeSettings:
    start_date: date

    def as_dict(self) -> dict[str, str]:
        return {"CHALLENGE_START_DATE": self.start_date.isoformat()}


@dataclass(frozen=True)
class TranscriptionSettings:
    provider: str
    api_key: str | None = None
    yandex_folder_id: str | None = None
    yandex_iam_token: str | None = None
    yandex_service_account_key_path: Path | None = None
    operation_timeout_seconds: int = 120
    poll_interval_seconds: float = 2.0

    def as_dict(self) -> dict[str, str | int | float | None]:
        return {
            "TRANSCRIPTION_PROVIDER": self.provider,
            "TRANSCRIPTION_API_KEY": self.api_key,
            "YANDEX_SPEECHKIT_FOLDER_ID": self.yandex_folder_id,
            "YANDEX_SPEECHKIT_IAM_TOKEN": self.yandex_iam_token,
            "YANDEX_SPEECHKIT_SERVICE_ACCOUNT_KEY_PATH": (
                str(self.yandex_service_account_key_path)
                if self.yandex_service_account_key_path is not None
                else None
            ),
            "YANDEX_SPEECHKIT_OPERATION_TIMEOUT_SECONDS": self.operation_timeout_seconds,
            "YANDEX_SPEECHKIT_POLL_INTERVAL_SECONDS": self.poll_interval_seconds,
        }


@dataclass(frozen=True)
class Settings:
    telegram: TelegramSettings
    telegram_runtime: TelegramRuntimeSettings
    google_sheets: GoogleSheetsSettings
    admin: AdminSettings
    storage: StorageSettings
    runtime: RuntimeSettings
    challenge: ChallengeSettings
    transcription: TranscriptionSettings

    def as_dict(self) -> dict[str, object]:
        return {
            "telegram": self.telegram.as_dict(),
            "telegram_runtime": self.telegram_runtime.as_dict(),
            "google_sheets": self.google_sheets.as_dict(),
            "admin": self.admin.as_dict(),
            "storage": self.storage.as_dict(),
            "runtime": self.runtime.as_dict(),
            "challenge": self.challenge.as_dict(),
            "transcription": self.transcription.as_dict(),
        }


def load_settings(
    *,
    environ: Mapping[str, str] | None = None,
    env_file: Path | str | None = ".env",
    strict: bool = True,
) -> Settings:
    """Load settings from an optional .env file and process environment."""

    values: dict[str, str] = {}
    if env_file is not None:
        values.update(_read_env_file(Path(env_file)))
    values.update(dict(os.environ if environ is None else environ))

    missing = _missing_required_values(values, strict=strict)
    if missing:
        raise ConfigurationError(f"Missing required settings: {', '.join(missing)}")

    return Settings(
        telegram=TelegramSettings(
            main_bot_token=_optional_value(values, "MAIN_TELEGRAM_BOT_TOKEN"),
            error_bot_token=_optional_value(values, "ERROR_TELEGRAM_BOT_TOKEN"),
            notification_bot_token=_optional_value(values, "NOTIFICATION_TELEGRAM_BOT_TOKEN"),
        ),
        telegram_runtime=TelegramRuntimeSettings(
            poll_timeout_seconds=_positive_int(
                values,
                "TELEGRAM_POLL_TIMEOUT_SECONDS",
                default=20,
            ),
            poll_limit=_positive_int(values, "TELEGRAM_POLL_LIMIT", default=100),
            request_timeout_seconds=_positive_int(
                values,
                "TELEGRAM_REQUEST_TIMEOUT_SECONDS",
                default=30,
            ),
        ),
        google_sheets=GoogleSheetsSettings(
            sheet_id=_required_value(values, "GOOGLE_SHEETS_ID"),
            challenge_flows_sheet_id=_required_value(values, "CHALLENGE_FLOWS_SHEETS_ID"),
            application_credentials=Path(_required_value(values, "GOOGLE_APPLICATION_CREDENTIALS")),
        ),
        admin=AdminSettings(
            admin_telegram_id=_required_int(values, "ADMIN_TELEGRAM_ID"),
            admin_error_chat_id=_required_int(values, "ADMIN_ERROR_CHAT_ID"),
            sitnikov_telegram_id=_required_int(values, "SITNIKOV_TELEGRAM_ID"),
            ivan_larkin_telegram_id=_optional_int(values, "IVAN_LARKIN_TELEGRAM_ID"),
            maria_telegram_id=_optional_int(values, "MARIA_TELEGRAM_ID"),
        ),
        storage=StorageSettings(
            sqlite_db_path=Path(_required_value(values, "SQLITE_DB_PATH")),
            audio_storage_dir=Path(_required_value(values, "AUDIO_STORAGE_DIR")),
            pdf_storage_dir=Path(_required_value(values, "PDF_STORAGE_DIR")),
        ),
        runtime=RuntimeSettings(log_level=values.get("LOG_LEVEL", "INFO").upper()),
        challenge=ChallengeSettings(start_date=_date_value(values, "CHALLENGE_START_DATE")),
        transcription=_load_transcription_settings(values),
    )


def redact_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    lowered = value.lower()
    if any(part in lowered for part in SECRET_VALUE_PARTS):
        return REDACTED
    return value


def redact_mapping(value: object) -> object:
    if isinstance(value, Mapping):
        redacted: dict[object, object] = {}
        for key, nested_value in value.items():
            key_text = str(key).upper()
            if any(part in key_text for part in SECRET_KEY_PARTS):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact_mapping(nested_value)
        return redacted
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_mapping(item) for item in value)
    return redact_value(value)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values


def _missing_required_values(values: Mapping[str, str], *, strict: bool) -> list[str]:
    required = [
        "GOOGLE_SHEETS_ID",
        "CHALLENGE_FLOWS_SHEETS_ID",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "ADMIN_TELEGRAM_ID",
        "ADMIN_ERROR_CHAT_ID",
        "SITNIKOV_TELEGRAM_ID",
        "SQLITE_DB_PATH",
        "AUDIO_STORAGE_DIR",
        "PDF_STORAGE_DIR",
    ]
    if strict:
        required = [
            "MAIN_TELEGRAM_BOT_TOKEN",
            "ERROR_TELEGRAM_BOT_TOKEN",
            "NOTIFICATION_TELEGRAM_BOT_TOKEN",
            *required,
        ]
    return [key for key in required if not _optional_value(values, key)]


def _optional_value(values: Mapping[str, str], key: str) -> str | None:
    value = values.get(key)
    if value is None or value == "":
        return None
    return value


def _date_value(values: Mapping[str, str], key: str) -> date:
    value = _optional_value(values, key)
    if value is None:
        return DEFAULT_CHALLENGE_START_DATE
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(f"{key} must be an ISO date YYYY-MM-DD") from exc


def _required_value(values: Mapping[str, str], key: str) -> str:
    value = _optional_value(values, key)
    if value is None:
        raise ConfigurationError(f"Missing required setting: {key}")
    return value


def _required_int(values: Mapping[str, str], key: str) -> int:
    value = _required_value(values, key)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"Setting {key} must be an integer") from exc


def _optional_int(values: Mapping[str, str], key: str) -> int | None:
    value = _optional_value(values, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"Setting {key} must be an integer") from exc


def _positive_int(values: Mapping[str, str], key: str, *, default: int) -> int:
    value = _optional_value(values, key)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigurationError(f"Setting {key} must be a positive integer") from exc
    if parsed <= 0:
        raise ConfigurationError(f"Setting {key} must be a positive integer")
    return parsed


def _positive_float(values: Mapping[str, str], key: str, *, default: float) -> float:
    value = _optional_value(values, key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ConfigurationError(f"Setting {key} must be a positive number") from exc
    if parsed <= 0:
        raise ConfigurationError(f"Setting {key} must be a positive number")
    return parsed


def _load_transcription_settings(values: Mapping[str, str]) -> TranscriptionSettings:
    provider = (_optional_value(values, "TRANSCRIPTION_PROVIDER") or "fake").strip().lower()
    if provider == "fake":
        return TranscriptionSettings(provider=provider)
    if provider != "yandex":
        raise ConfigurationError(
            "Setting TRANSCRIPTION_PROVIDER must be one of: fake, yandex"
        )

    missing = [
        key
        for key in ("TRANSCRIPTION_API_KEY", "YANDEX_SPEECHKIT_FOLDER_ID")
        if _optional_value(values, key) is None
    ]
    if missing:
        raise ConfigurationError(f"Missing required settings: {', '.join(missing)}")

    service_account_key = _optional_value(values, "YANDEX_SPEECHKIT_SERVICE_ACCOUNT_KEY_PATH")
    return TranscriptionSettings(
        provider=provider,
        api_key=_required_value(values, "TRANSCRIPTION_API_KEY"),
        yandex_folder_id=_required_value(values, "YANDEX_SPEECHKIT_FOLDER_ID"),
        yandex_iam_token=_optional_value(values, "YANDEX_SPEECHKIT_IAM_TOKEN"),
        yandex_service_account_key_path=(
            Path(service_account_key) if service_account_key is not None else None
        ),
        operation_timeout_seconds=_positive_int(
            values,
            "YANDEX_SPEECHKIT_OPERATION_TIMEOUT_SECONDS",
            default=120,
        ),
        poll_interval_seconds=_positive_float(
            values,
            "YANDEX_SPEECHKIT_POLL_INTERVAL_SECONDS",
            default=2.0,
        ),
    )
