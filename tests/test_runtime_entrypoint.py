from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.config import load_settings
from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import CONSENT_ACCEPT_CALLBACK
from app.runtime import RuntimeNotImplementedError, TelegramUpdateDispatcher, initialize_runtime, main, run_bot
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import FlowResponse, TelegramUserContext
from app.services.voice_messages import VoiceMessageInput
from app.storage.dialog_state import DialogState, DialogStateRepository
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
        "TRANSCRIPTION_PROVIDER": "yandex",
        "TRANSCRIPTION_API_KEY": "yandex-api-key-123",
        "YANDEX_SPEECHKIT_FOLDER_ID": "folder-123",
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


def test_runtime_env_includes_transcription_provider_config(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))

    assert settings.transcription.provider == "yandex"
    assert settings.transcription.api_key == "yandex-api-key-123"
    assert settings.transcription.yandex_folder_id == "folder-123"


def test_dispatcher_routes_start_to_participant_flow(tmp_path: Path) -> None:
    dispatcher, services, _error_bot = _dispatcher(tmp_path)

    dispatcher.dispatch_update(_message_update(text="/start"))

    assert services.participant.starts == [
        (
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001"),
            NOW.isoformat(),
        )
    ]


def test_dispatcher_routes_weekly_text_to_active_report(tmp_path: Path) -> None:
    dispatcher, services, _error_bot = _dispatcher(tmp_path)
    _state(dispatcher.dialog_states, flow="weekly_report", step="text")

    dispatcher.dispatch_update(_message_update(text="Отчёт текстом", message_id=601))

    assert services.weekly.text_messages == [
        (
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001"),
            "Отчёт текстом",
            601,
        )
    ]


def test_dispatcher_routes_insight_text_to_active_insight(tmp_path: Path) -> None:
    dispatcher, services, _error_bot = _dispatcher(tmp_path)
    _state(dispatcher.dialog_states, flow="insight", step="text")

    dispatcher.dispatch_update(_message_update(text="Инсайт текстом", message_id=602))

    assert services.insights.text_messages == [
        (
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001"),
            "Инсайт текстом",
            602,
        )
    ]


def test_dispatcher_routes_voice_to_active_draft_service(tmp_path: Path) -> None:
    dispatcher, services, _error_bot = _dispatcher(tmp_path)
    _state(dispatcher.dialog_states, flow="weekly_report", step="text")

    dispatcher.dispatch_update(_voice_update(file_id="voice-file-1", duration=42, message_id=603))

    assert services.weekly.voices == [
        (
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001"),
            "voice-file-1",
            42,
            603,
        )
    ]


def test_dispatcher_sanitizes_malformed_callback_error(tmp_path: Path) -> None:
    dispatcher, _services, error_bot = _dispatcher(tmp_path)

    dispatcher.dispatch_update(_callback_update(data="bad:yandex-api-key-123:personal report text"))

    assert len(error_bot.sent_messages) == 1
    error_text = error_bot.sent_messages[0].text
    assert "malformed_callback" in error_text
    assert "bad:yandex-api-key-123:personal report text" not in error_text
    assert "yandex-api-key-123" not in error_text
    assert "personal report text" not in error_text


def test_dispatcher_routes_consent_callback(tmp_path: Path) -> None:
    dispatcher, services, _error_bot = _dispatcher(tmp_path)

    dispatcher.dispatch_update(_callback_update(data=CONSENT_ACCEPT_CALLBACK))

    assert services.participant.consents == [
        (
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001"),
            NOW.isoformat(),
        )
    ]


NOW = datetime(2026, 7, 5, 18, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))


@dataclass
class RuntimeServices:
    participant: "RecordingParticipantService" = field(default_factory=lambda: RecordingParticipantService())
    weekly: "RecordingWeeklyReportService" = field(default_factory=lambda: RecordingWeeklyReportService())
    insights: "RecordingInsightService" = field(default_factory=lambda: RecordingInsightService())
    captains: "RecordingCaptainService" = field(default_factory=lambda: RecordingCaptainService())


def _dispatcher(
    tmp_path: Path,
) -> tuple[TelegramUpdateDispatcher, RuntimeServices, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    from app.storage.sqlite import initialize_schema

    initialize_schema(db_path)
    services = RuntimeServices()
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=error_bot,
        notification_bot=FakeBotClient(BotPurpose.NOTIFICATION),
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    dispatcher = TelegramUpdateDispatcher(
        participant_service=services.participant,
        weekly_report_service=services.weekly,
        insight_service=services.insights,
        captain_service=services.captains,
        dialog_states=DialogStateRepository(db_path),
        notification_router=router,
        now_provider=lambda: NOW,
    )
    return dispatcher, services, error_bot


def _state(
    repository: DialogStateRepository,
    *,
    flow: str,
    step: str,
    draft_id: str | None = None,
) -> None:
    repository.upsert(
        DialogState(
            telegram_id=1001,
            participant_id="P001",
            role="participant",
            flow=flow,
            step=step,
            draft_id=draft_id,
            started_at=NOW.isoformat(),
            updated_at=NOW.isoformat(),
        )
    )


def _message_update(*, text: str, message_id: int = 600) -> dict[str, object]:
    return {
        "update_id": 10,
        "message": {
            "message_id": message_id,
            "date": int(NOW.timestamp()),
            "chat": {"id": "chat-1001"},
            "from": {"id": 1001, "username": "p001"},
            "text": text,
        },
    }


def _voice_update(*, file_id: str, duration: int, message_id: int) -> dict[str, object]:
    return {
        "update_id": 11,
        "message": {
            "message_id": message_id,
            "date": int(NOW.timestamp()),
            "chat": {"id": "chat-1001"},
            "from": {"id": 1001, "username": "p001"},
            "voice": {"file_id": file_id, "duration": duration},
        },
    }


def _callback_update(*, data: str) -> dict[str, object]:
    return {
        "update_id": 12,
        "callback_query": {
            "id": "callback-1",
            "from": {"id": 1001, "username": "p001"},
            "message": {
                "message_id": 604,
                "chat": {"id": "chat-1001"},
            },
            "data": data,
        },
    }


class RecordingParticipantService:
    def __init__(self) -> None:
        self.starts: list[tuple[TelegramUserContext, str]] = []
        self.consents: list[tuple[TelegramUserContext, str]] = []

    def handle_start(self, user: TelegramUserContext, *, occurred_at: str) -> FlowResponse:
        self.starts.append((user, occurred_at))
        return FlowResponse(chat_id=user.chat_id, text="start")

    def accept_consent(self, user: TelegramUserContext, *, consent_given_at: str) -> FlowResponse:
        self.consents.append((user, consent_given_at))
        return FlowResponse(chat_id=user.chat_id, text="consent")


class RecordingWeeklyReportService:
    def __init__(self) -> None:
        self.text_messages: list[tuple[TelegramUserContext, str, int | None]] = []
        self.voices: list[tuple[TelegramUserContext, str, int, int | None]] = []

    def add_text_message(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        self.text_messages.append((user, text, telegram_message_id))
        return FlowResponse(chat_id=user.chat_id, text="weekly text")

    def add_voice_message(
        self,
        user: TelegramUserContext,
        *,
        telegram_file_id: str,
        duration_seconds: int,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        self.voices.append((user, telegram_file_id, duration_seconds, telegram_message_id))
        return FlowResponse(chat_id=user.chat_id, text="weekly voice")


class RecordingInsightService:
    def __init__(self) -> None:
        self.text_messages: list[tuple[TelegramUserContext, str, int | None]] = []
        self.voices: list[VoiceMessageInput] = []

    def add_text_message(
        self,
        user: TelegramUserContext,
        text: str,
        *,
        now: datetime,
        telegram_message_id: int | None = None,
    ) -> FlowResponse:
        self.text_messages.append((user, text, telegram_message_id))
        return FlowResponse(chat_id=user.chat_id, text="insight text")


class RecordingCaptainService:
    pass
