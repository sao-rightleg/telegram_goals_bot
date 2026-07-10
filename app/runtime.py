"""Production runtime readiness helpers and CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import signal
import sys
from pathlib import Path
from threading import Event
from typing import Callable, Protocol, Sequence

import httpx

from app.bot.clients import BotPurpose, LiveTelegramBotClient, LiveTelegramFileDownloader
from app.logging import setup_logging
from app.bot.dispatch import TelegramUpdate, TelegramUpdateDispatcher, parse_telegram_update
from app.config import ConfigurationError, Settings, load_settings
from app.services.captains import CaptainService
from app.services.insights import InsightService
from app.services.notifications import NotificationCategory, NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.voice_messages import VoiceMessageService
from app.services.weekly_reports import WeeklyReportService
from app.sheets.gateway import GoogleSheetsError, GoogleSheetsGateway, validate_required_schema
from app.speech.transcription import FakeSpeechTranscriber, YandexSpeechKitTranscriber
from app.storage.dialog_state import DialogStateRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.paths import StoragePathPolicy
from app.storage.sqlite import REQUIRED_TECHNICAL_TABLES, initialize_schema, list_tables
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


@dataclass(frozen=True)
class RuntimeInitializationResult:
    sqlite_db_path: Path
    created_storage_dirs: tuple[Path, ...]
    technical_tables: frozenset[str]


@dataclass(frozen=True)
class RuntimeComponents:
    main_bot: LiveTelegramBotClient
    error_bot: LiveTelegramBotClient
    notification_bot: LiveTelegramBotClient
    notification_router: NotificationRouter
    dispatcher: TelegramUpdateDispatcher
    participant_service: ParticipantFlowService
    weekly_report_service: WeeklyReportService
    insight_service: InsightService
    captain_service: CaptainService
    sheets_gateway: GoogleSheetsGateway
    voice_service: VoiceMessageService

    def with_replacements(self, **changes: object) -> "RuntimeComponents":
        return replace(self, **changes)


class PollingRunner(Protocol):
    def run(self, components: RuntimeComponents) -> None:
        """Run Telegram polling until stopped."""


GoogleServiceFactory = Callable[[Settings], object]
SchemaValidator = Callable[..., None]
RuntimeComponentsFactory = Callable[[Settings], RuntimeComponents]
ReadinessValidator = Callable[[Settings], None]


def initialize_runtime(settings: Settings) -> RuntimeInitializationResult:
    """Prepare local technical storage for the production runtime."""

    storage_dirs = (
        settings.storage.sqlite_db_path.parent,
        settings.storage.audio_storage_dir,
        settings.storage.pdf_storage_dir,
    )
    for directory in storage_dirs:
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(0o700)

    initialize_schema(settings.storage.sqlite_db_path)
    settings.storage.sqlite_db_path.chmod(0o600)
    tables = frozenset(list_tables(settings.storage.sqlite_db_path))
    missing_tables = REQUIRED_TECHNICAL_TABLES - tables
    if missing_tables:
        missing_text = ", ".join(sorted(missing_tables))
        raise ConfigurationError(f"SQLite schema initialization incomplete: {missing_text}")

    return RuntimeInitializationResult(
        sqlite_db_path=settings.storage.sqlite_db_path,
        created_storage_dirs=storage_dirs,
        technical_tables=tables,
    )


def validate_runtime_readiness(
    settings: Settings,
    *,
    google_service_factory: GoogleServiceFactory | None = None,
    schema_validator: SchemaValidator | None = None,
) -> None:
    """Validate non-destructive runtime readiness before polling starts."""

    if not settings.google_sheets.application_credentials.is_file():
        raise ConfigurationError(
            "Google credentials file is missing: GOOGLE_APPLICATION_CREDENTIALS"
        )

    try:
        selected_google_service_factory = google_service_factory or create_google_sheets_service
        google_service = selected_google_service_factory(settings)
        if schema_validator is None:
            schema_validator = validate_required_schema
        schema_validator(
            google_service,
            spreadsheet_id=settings.google_sheets.sheet_id,
        )
        _build_transcriber(settings, http_client=httpx.Client())
    except ConfigurationError:
        raise
    except GoogleSheetsError as exc:
        raise ConfigurationError(str(exc)) from exc
    except Exception as exc:
        raise ConfigurationError(f"Runtime readiness failed: {type(exc).__name__}") from exc


def compose_runtime(
    settings: Settings,
    *,
    google_service_factory: GoogleServiceFactory | None = None,
) -> RuntimeComponents:
    """Wire live adapters, repositories, services, and dispatcher."""

    selected_google_service_factory = google_service_factory or create_google_sheets_service
    request_timeout = settings.telegram_runtime.request_timeout_seconds
    main_http = httpx.Client(timeout=request_timeout)
    error_http = httpx.Client(timeout=request_timeout)
    notification_http = httpx.Client(timeout=request_timeout)
    file_http = httpx.Client(timeout=request_timeout)
    speech_http = httpx.Client()

    main_bot = LiveTelegramBotClient(
        purpose=BotPurpose.MAIN,
        token=_required_token(settings.telegram.main_bot_token, "MAIN_TELEGRAM_BOT_TOKEN"),
        http_client=main_http,
    )
    error_bot = LiveTelegramBotClient(
        purpose=BotPurpose.ERROR,
        token=_required_token(settings.telegram.error_bot_token, "ERROR_TELEGRAM_BOT_TOKEN"),
        http_client=error_http,
    )
    notification_bot = LiveTelegramBotClient(
        purpose=BotPurpose.NOTIFICATION,
        token=_required_token(
            settings.telegram.notification_bot_token,
            "NOTIFICATION_TELEGRAM_BOT_TOKEN",
        ),
        http_client=notification_http,
    )
    notification_router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(
            RecipientType.ADMIN_ERROR_CHAT,
            str(settings.admin.admin_error_chat_id),
        ),
    )

    db_path = settings.storage.sqlite_db_path
    dialog_states = DialogStateRepository(db_path)
    weekly_drafts = WeeklyReportDraftRepository(db_path)
    insight_drafts = InsightDraftRepository(db_path)
    sheets_gateway = GoogleSheetsGateway(
        service=selected_google_service_factory(settings),
        spreadsheet_id=settings.google_sheets.sheet_id,
    )
    voice_service = VoiceMessageService(
        dialog_states=dialog_states,
        weekly_report_drafts=weekly_drafts,
        insight_drafts=insight_drafts,
        path_policy=StoragePathPolicy(
            audio_root=settings.storage.audio_storage_dir,
            sqlite_root=settings.storage.sqlite_db_path.parent,
            pdf_root=settings.storage.pdf_storage_dir,
        ),
        file_downloader=LiveTelegramFileDownloader(
            token=_required_token(settings.telegram.main_bot_token, "MAIN_TELEGRAM_BOT_TOKEN"),
            http_client=file_http,
        ),
        transcriber=_build_transcriber(settings, http_client=speech_http),
        notification_router=notification_router,
    )
    participant_service = ParticipantFlowService(
        sheets=sheets_gateway,
        main_bot=main_bot,
        notification_router=notification_router,
        dialog_states=dialog_states,
    )
    weekly_report_service = WeeklyReportService(
        sheets=sheets_gateway,
        main_bot=main_bot,
        notification_router=notification_router,
        drafts=weekly_drafts,
        voice_messages=voice_service,
    )
    insight_service = InsightService(
        sheets=sheets_gateway,
        main_bot=main_bot,
        notification_router=notification_router,
        drafts=insight_drafts,
        voice_messages=voice_service,
    )
    captain_service = CaptainService(
        sheets=sheets_gateway,
        main_bot=main_bot,
        notification_router=notification_router,
        drafts=weekly_drafts,
    )
    dispatcher = TelegramUpdateDispatcher(
        participant_service=participant_service,
        weekly_report_service=weekly_report_service,
        insight_service=insight_service,
        captain_service=captain_service,
        dialog_states=dialog_states,
        notification_router=notification_router,
    )
    return RuntimeComponents(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        notification_router=notification_router,
        dispatcher=dispatcher,
        participant_service=participant_service,
        weekly_report_service=weekly_report_service,
        insight_service=insight_service,
        captain_service=captain_service,
        sheets_gateway=sheets_gateway,
        voice_service=voice_service,
    )


@dataclass
class TelegramPollingRunner:
    poll_timeout_seconds: int
    poll_limit: int
    stop_event: Event

    def run(self, components: RuntimeComponents) -> None:
        offset: int | None = None
        while not self.stop_event.is_set():
            try:
                updates = components.main_bot.get_updates(
                    offset=offset,
                    timeout_seconds=self.poll_timeout_seconds,
                    limit=self.poll_limit,
                )
            except Exception as exc:
                _notify_polling_error(
                    components.notification_router,
                    event="telegram_get_updates_failed",
                    error=exc,
                )
                continue

            for update in updates:
                update_id = update.get("update_id")
                try:
                    components.dispatcher.dispatch_update(update)
                except Exception as exc:
                    _notify_polling_error(
                        components.notification_router,
                        event="telegram_update_dispatch_failed",
                        error=exc,
                        update_id=update_id if isinstance(update_id, int) else None,
                    )
                if isinstance(update_id, int):
                    offset = update_id + 1


def run_bot(
    settings: Settings,
    *,
    components_factory: RuntimeComponentsFactory | None = None,
    polling_runner: PollingRunner | None = None,
    google_service_factory: GoogleServiceFactory | None = None,
) -> None:
    """Run the live Telegram polling runtime."""

    initialize_runtime(settings)
    if components_factory is None:
        try:
            validate_runtime_readiness(
                settings,
                google_service_factory=google_service_factory,
            )
        except Exception as exc:
            _notify_startup_readiness_failure(settings, exc)
            raise
        components_factory = lambda runtime_settings: compose_runtime(
            runtime_settings,
            google_service_factory=google_service_factory,
        )

    components = components_factory(settings)
    if polling_runner is None:
        stop_event = Event()
        _install_shutdown_handlers(stop_event)
        polling_runner = TelegramPollingRunner(
            poll_timeout_seconds=settings.telegram_runtime.poll_timeout_seconds,
            poll_limit=settings.telegram_runtime.poll_limit,
            stop_event=stop_event,
        )
    polling_runner.run(components)


def main(
    argv: Sequence[str] | None = None,
    *,
    google_service_factory: GoogleServiceFactory | None = None,
) -> int:
    parser = argparse.ArgumentParser(prog="telegram-goals-bot")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file. Use an empty string to disable file loading.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-config", help="Load config and initialize technical storage.")
    subparsers.add_parser("init-storage", help="Create local storage directories and SQLite schema.")
    subparsers.add_parser("run", help="Start live bot runtime after adapters are implemented.")

    args = parser.parse_args(list(argv) if argv is not None else None)
    env_file = None if args.env_file == "" else args.env_file

    try:
        settings = load_settings(env_file=env_file, strict=True)
        logger = setup_logging(settings)
        result = initialize_runtime(settings)
        logger.info("runtime storage ready", extra={"sqlite_db_path": str(result.sqlite_db_path)})

        if args.command == "check-config":
            validate_runtime_readiness(settings, google_service_factory=google_service_factory)
            return 0
        if args.command == "init-storage":
            return 0
        if args.command == "run":
            run_bot(settings, google_service_factory=google_service_factory)
            return 0
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 2


def create_google_sheets_service(settings: Settings) -> object:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        str(settings.google_sheets.application_credentials),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _build_transcriber(settings: Settings, *, http_client: httpx.Client):
    transcription = settings.transcription
    if transcription.provider == "fake":
        return FakeSpeechTranscriber(transcription_text="")
    if transcription.provider == "yandex":
        return YandexSpeechKitTranscriber(
            api_key=transcription.api_key,
            iam_token=transcription.yandex_iam_token,
            folder_id=transcription.yandex_folder_id or "",
            operation_timeout_seconds=transcription.operation_timeout_seconds,
            poll_interval_seconds=transcription.poll_interval_seconds,
            http_client=http_client,
        )
    raise ConfigurationError("Unsupported transcription provider")


def _required_token(value: str | None, key: str) -> str:
    if not value:
        raise ConfigurationError(f"Missing required setting: {key}")
    return value


def _notify_startup_readiness_failure(settings: Settings, error: Exception) -> None:
    if not settings.telegram.error_bot_token:
        return
    try:
        error_bot = LiveTelegramBotClient(
            purpose=BotPurpose.ERROR,
            token=settings.telegram.error_bot_token,
            http_client=httpx.Client(timeout=settings.telegram_runtime.request_timeout_seconds),
        )
        router = NotificationRouter(
            main_bot=error_bot,
            error_bot=error_bot,
            notification_bot=error_bot,
            admin_error_recipient=Recipient(
                RecipientType.ADMIN_ERROR_CHAT,
                str(settings.admin.admin_error_chat_id),
            ),
        )
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=f"runtime_startup_readiness_failed error_type={type(error).__name__}",
            recipients=(),
        )
    except Exception:
        return


def _notify_polling_error(
    router: NotificationRouter,
    *,
    event: str,
    error: Exception,
    update_id: int | None = None,
) -> None:
    parts = [event, f"error_type={type(error).__name__}"]
    if update_id is not None:
        parts.append(f"update_id={update_id}")
    router.send(
        category=NotificationCategory.TECHNICAL_ERROR,
        text=" ".join(parts),
        recipients=(),
    )


def _install_shutdown_handlers(stop_event: Event) -> None:
    def _stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
