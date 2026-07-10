from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
import stat
from zoneinfo import ZoneInfo

import pytest

import app.runtime as runtime_module
from app.config import ConfigurationError, load_settings
from app.bot.clients import BotPurpose, FakeBotClient, TelegramApiError
from app.bot.menus import CONSENT_ACCEPT_CALLBACK
from app.runtime import (
    RuntimeComponents,
    TelegramUpdateDispatcher,
    compose_runtime,
    initialize_runtime,
    main,
    run_bot,
    TelegramPollingRunner,
    validate_runtime_readiness,
)
from app.sheets.gateway import GoogleSheetsSchemaError
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


def test_initialize_runtime_restricts_sensitive_storage_permissions(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))

    initialize_runtime(settings)

    for directory in (
        settings.storage.sqlite_db_path.parent,
        settings.storage.audio_storage_dir,
        settings.storage.pdf_storage_dir,
    ):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(settings.storage.sqlite_db_path.stat().st_mode) == 0o600


def test_run_bot_starts_controlled_fake_runtime(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))

    runner = RecordingPollingRunner()

    run_bot(
        settings,
        components_factory=lambda _settings: _runtime_components(tmp_path),
        polling_runner=runner,
    )

    assert runner.started is True
    assert isinstance(runner.components.dispatcher, TelegramUpdateDispatcher)


def test_run_bot_no_longer_raises_not_implemented_with_fake_runtime(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))
    runner = RecordingPollingRunner()

    run_bot(
        settings,
        components_factory=lambda _settings: _runtime_components(tmp_path),
        polling_runner=runner,
    )

    assert runner.started is True


def test_check_config_runs_google_schema_validation(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))
    settings.google_sheets.application_credentials.write_text("{}", encoding="utf-8")
    service = object()
    calls: list[tuple[object, str]] = []

    validate_runtime_readiness(
        settings,
        google_service_factory=lambda _settings: service,
        schema_validator=lambda google_service, *, spreadsheet_id: calls.append(
            (google_service, spreadsheet_id)
        ),
    )

    assert calls == [(service, "sheet-id")]


def test_run_bot_composes_three_bot_router_and_services(tmp_path: Path) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))
    components = compose_runtime(
        settings,
        google_service_factory=lambda _settings: _fake_google_service(),
    )

    assert components.main_bot.purpose is BotPurpose.MAIN
    assert components.error_bot.purpose is BotPurpose.ERROR
    assert components.notification_bot.purpose is BotPurpose.NOTIFICATION
    assert components.notification_router.main_bot is components.main_bot
    assert components.notification_router.error_bot is components.error_bot
    assert components.notification_router.notification_bot is components.notification_bot
    assert components.dispatcher.participant_service is components.participant_service
    assert components.dispatcher.weekly_report_service is components.weekly_report_service
    assert components.dispatcher.insight_service is components.insight_service
    assert components.dispatcher.captain_service is components.captain_service


def test_cli_check_config_uses_env_file_and_initializes_storage(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in runtime_env(tmp_path).items()),
        encoding="utf-8",
    )
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")

    exit_code = main(
        ["--env-file", str(env_file), "check-config"],
        google_service_factory=lambda _settings: _fake_google_service(),
    )

    assert exit_code == 0
    assert (tmp_path / "data" / "sqlite" / "bot.sqlite3").exists()


def test_cli_check_config_returns_clear_error_for_google_schema_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{key}={value}" for key, value in runtime_env(tmp_path).items()),
        encoding="utf-8",
    )
    (tmp_path / "credentials.json").write_text("{}", encoding="utf-8")

    def broken_schema_service(_settings):
        raise GoogleSheetsSchemaError("Missing required Google Sheets tabs: Participants")

    exit_code = main(
        ["--env-file", str(env_file), "check-config"],
        google_service_factory=broken_schema_service,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Missing required Google Sheets tabs: Participants" in captured.err
    assert "Traceback" not in captured.err


def test_run_bot_notifies_startup_readiness_failure_without_raw_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(environ=runtime_env(tmp_path))
    settings.google_sheets.application_credentials.write_text("{}", encoding="utf-8")
    error_bot = FakeBotClient(BotPurpose.ERROR)

    def fake_error_bot_client(*, purpose: BotPurpose, token: str, http_client: object) -> FakeBotClient:
        assert purpose is BotPurpose.ERROR
        assert token == "error-token-456"
        return error_bot

    def broken_schema_service(_settings):
        raise GoogleSheetsSchemaError("Missing Participants yandex-api-key-123 personal report text")

    monkeypatch.setattr(runtime_module, "LiveTelegramBotClient", fake_error_bot_client)

    with pytest.raises(ConfigurationError):
        run_bot(settings, google_service_factory=broken_schema_service)

    assert len(error_bot.sent_messages) == 1
    error_text = error_bot.sent_messages[0].text
    assert "runtime_startup_readiness_failed" in error_text
    assert "ConfigurationError" in error_text
    assert "yandex-api-key-123" not in error_text
    assert "personal report text" not in error_text
    assert "Missing Participants" not in error_text


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


def test_polling_runner_reports_dispatch_error_and_continues_without_raw_update(tmp_path: Path) -> None:
    components = _runtime_components(tmp_path)
    dispatcher, services, _dispatcher_error_bot = _dispatcher(tmp_path)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    components = components.with_replacements(
        main_bot=PollingBot(
            updates=[
                _message_update(text="/boom", message_id=701, update_id=100),
                _message_update(text="/start", message_id=702, update_id=101),
            ]
        ),
        error_bot=error_bot,
        notification_router=_router(error_bot=error_bot),
        dispatcher=FailingOnceDispatcher(dispatcher),
    )
    runner = TelegramPollingRunner(poll_timeout_seconds=1, poll_limit=100, stop_event=StopAfterCalls(limit=2))

    runner.run(components)

    assert components.main_bot.offsets == [None, 101]
    assert len(error_bot.sent_messages) == 1
    error_text = error_bot.sent_messages[0].text
    assert "telegram_update_dispatch_failed" in error_text
    assert "RuntimeError" in error_text
    assert "/boom" not in error_text
    assert "personal report text" not in error_text
    assert services.participant.starts


def test_polling_runner_does_not_advance_offset_when_get_updates_fails(tmp_path: Path) -> None:
    components = _runtime_components(tmp_path)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    components = components.with_replacements(
        main_bot=FailingPollingBot(),
        error_bot=error_bot,
        notification_router=_router(error_bot=error_bot),
    )
    runner = TelegramPollingRunner(poll_timeout_seconds=1, poll_limit=100, stop_event=StopAfterCalls(limit=1))

    runner.run(components)

    assert components.main_bot.offsets == [None]
    assert len(error_bot.sent_messages) == 1
    assert "telegram_get_updates_failed" in error_bot.sent_messages[0].text
    assert "poll-token-123" not in error_bot.sent_messages[0].text


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


def _message_update(*, text: str, message_id: int = 600, update_id: int = 10) -> dict[str, object]:
    return {
        "update_id": update_id,
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


def _router(*, error_bot: FakeBotClient) -> NotificationRouter:
    return NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=error_bot,
        notification_bot=FakeBotClient(BotPurpose.NOTIFICATION),
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )


@dataclass(frozen=True)
class StopAfterCalls:
    limit: int
    calls: int = 0

    def is_set(self) -> bool:
        object.__setattr__(self, "calls", self.calls + 1)
        return self.calls > self.limit


@dataclass
class PollingBot(FakeBotClient):
    updates: list[dict[str, object]] = field(default_factory=list)
    offsets: list[int | None] = field(default_factory=list)

    def __init__(self, updates: list[dict[str, object]]) -> None:
        super().__init__(BotPurpose.MAIN)
        self.updates = updates
        self.offsets = []

    def get_updates(self, *, offset: int | None, timeout_seconds: int, limit: int) -> list[dict[str, object]]:
        self.offsets.append(offset)
        if self.updates:
            return [self.updates.pop(0)]
        return []


class FailingPollingBot(FakeBotClient):
    def __init__(self) -> None:
        super().__init__(BotPurpose.MAIN)
        self.offsets: list[int | None] = []

    def get_updates(self, *, offset: int | None, timeout_seconds: int, limit: int) -> list[dict[str, object]]:
        self.offsets.append(offset)
        raise TelegramApiError("Telegram getUpdates request failed: poll-token-123")


@dataclass
class FailingOnceDispatcher:
    delegate: TelegramUpdateDispatcher
    failed: bool = False

    def dispatch_update(self, payload: dict[str, object]) -> FlowResponse | None:
        if not self.failed:
            self.failed = True
            raise RuntimeError("personal report text /boom")
        return self.delegate.dispatch_update(payload)


class RecordingPollingRunner:
    def __init__(self) -> None:
        self.started = False
        self.components: RuntimeComponents | None = None

    def run(self, components: RuntimeComponents) -> None:
        self.started = True
        self.components = components


def _runtime_components(tmp_path: Path) -> RuntimeComponents:
    settings = load_settings(environ=runtime_env(tmp_path))
    return compose_runtime(settings, google_service_factory=lambda _settings: _fake_google_service())


def _fake_google_service() -> object:
    from tests.test_sheets_live_helpers import FakeSheetsService, minimal_live_sheets

    return FakeSheetsService(minimal_live_sheets())
