"""Production runtime readiness helpers and CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
import logging
import signal
import sys
from pathlib import Path
from threading import Event, Thread
from typing import Callable, Protocol, Sequence
from zoneinfo import ZoneInfo

import httpx

from app.bot.clients import BotCommand, BotPurpose, LiveTelegramBotClient, LiveTelegramFileDownloader
from app.logging import setup_logging
from app.bot.dispatch import TelegramUpdate, TelegramUpdateDispatcher, parse_telegram_update
from app.config import ConfigurationError, Settings, load_settings
from app.scheduler.calendar import TIMEZONE_NAME, ScheduleItem, reminder_schedule
from app.scheduler.calendar import configure_challenge_calendar
from app.scheduler.jobs import SchedulerService
from app.services.captains import CaptainService
from app.services.insights import InsightService
from app.services.notifications import NotificationCategory, NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.voice_messages import VoiceMessageService
from app.services.weekly_reports import WeeklyReportService
from app.sheets.gateway import (
    GoogleSheetsError,
    GoogleSheetsGateway,
    validate_challenge_flows_schema,
    validate_required_schema,
)
from app.speech.transcription import FakeSpeechTranscriber, YandexSpeechKitTranscriber
from app.storage.dialog_state import DialogStateRepository
from app.storage.registration import RegistrationDraftRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.paths import StoragePathPolicy
from app.storage.scheduler import SchedulerJobRepository
from app.storage.sqlite import REQUIRED_TECHNICAL_TABLES, initialize_schema, list_tables
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


logger = logging.getLogger("telegram_goals_bot")


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
    scheduler_service: SchedulerService

    def with_replacements(self, **changes: object) -> "RuntimeComponents":
        return replace(self, **changes)


class PollingRunner(Protocol):
    def run(self, components: RuntimeComponents) -> None:
        """Run Telegram polling until stopped."""


class SchedulerRunner(Protocol):
    def start(self, components: RuntimeComponents) -> None:
        """Start scheduled background jobs."""

    def stop(self) -> None:
        """Stop scheduled background jobs."""


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
        schema_validator_was_injected = schema_validator is not None
        if schema_validator is None:
            schema_validator = validate_required_schema
        schema_validator(
            google_service,
            spreadsheet_id=settings.google_sheets.sheet_id,
        )
        if not schema_validator_was_injected:
            validate_challenge_flows_schema(
                google_service,
                spreadsheet_id=settings.google_sheets.challenge_flows_sheet_id,
            )
            _configure_challenge_calendar_from_sheets(
                settings,
                GoogleSheetsGateway(
                    service=google_service,
                    spreadsheet_id=settings.google_sheets.challenge_flows_sheet_id,
                ),
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
    registration_drafts = RegistrationDraftRepository(db_path)
    weekly_drafts = WeeklyReportDraftRepository(db_path)
    insight_drafts = InsightDraftRepository(db_path)
    scheduler_jobs = SchedulerJobRepository(db_path)
    google_service = selected_google_service_factory(settings)
    sheets_gateway = GoogleSheetsGateway(
        service=google_service,
        spreadsheet_id=settings.google_sheets.sheet_id,
    )
    challenge_flows_gateway = GoogleSheetsGateway(
        service=google_service,
        spreadsheet_id=settings.google_sheets.challenge_flows_sheet_id,
    )
    _configure_challenge_calendar_from_sheets(settings, challenge_flows_gateway)
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
        registration_flows=challenge_flows_gateway,
        registration_drafts=registration_drafts,
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
    scheduler_service = SchedulerService(
        sheets=sheets_gateway,
        notification_router=notification_router,
        repository=scheduler_jobs,
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
        scheduler_service=scheduler_service,
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


@dataclass
class LiveSchedulerRunner:
    stop_event: Event
    check_interval_seconds: float = 30.0
    catch_up_window: timedelta = timedelta(minutes=15)
    now_provider: Callable[[], datetime] | None = None

    def __post_init__(self) -> None:
        self._thread: Thread | None = None
        self._dispatched_keys: set[str] = set()

    def start(self, components: RuntimeComponents) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(
            target=self._run_loop,
            args=(components,),
            name="telegram-goals-bot-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.check_interval_seconds + 1.0))

    def run_due_jobs_once(self, components: RuntimeComponents, *, now: datetime | None = None) -> None:
        current = now or self._now()
        local_current = current.astimezone(ZoneInfo(TIMEZONE_NAME))
        schedule_rows = components.sheets_gateway.list_flow_schedule()
        dynamic_focus_defined = any(_is_valid_focus_schedule_row(row) for row in schedule_rows)
        for row in schedule_rows:
            scheduled_at = _flow_event_scheduled_at(row)
            if scheduled_at is None or row.get("is_enabled") is not True:
                continue
            if scheduled_at > local_current or local_current - scheduled_at > self.catch_up_window:
                continue
            event_id = str(row.get("event_id", "")).strip()
            dispatch_key = f"flow:{event_id}:{scheduled_at.isoformat()}"
            if not event_id or dispatch_key in self._dispatched_keys:
                continue
            self._dispatched_keys.add(dispatch_key)
            self._run_flow_schedule_event(components, row, scheduled_at=scheduled_at)

        for item in reminder_schedule():
            if dynamic_focus_defined and item.job_type in {
                "monday_reminder",
                "monday_focus_1300",
                "monday_focus_1900",
                "weekly_focus_summary_captain",
            }:
                continue
            scheduled_at = _last_scheduled_at(item, local_current)
            if scheduled_at is None:
                continue
            if local_current - scheduled_at > self.catch_up_window:
                continue

            dispatch_key = f"{item.job_type}:{scheduled_at.isoformat()}"
            if dispatch_key in self._dispatched_keys:
                continue

            self._dispatched_keys.add(dispatch_key)
            self._run_scheduler_job(components, item.job_type, scheduled_at=scheduled_at)

    def _run_flow_schedule_event(
        self,
        components: RuntimeComponents,
        row: dict[str, object],
        *,
        scheduled_at: datetime,
    ) -> None:
        event_type = str(row.get("event_type", "")).strip()
        recipient_role = str(row.get("recipient_role", "")).strip().lower()
        if event_type == "weekly_focus_prompt":
            if recipient_role not in {"участник", "participant"}:
                return
            reminder_type = _focus_reminder_type(row)
            components.scheduler_service.run_reminder(
                reminder_type,
                now=scheduled_at,
                flow_id=str(row.get("flow_id", "")).strip() or None,
                event_id=str(row.get("event_id", "")).strip(),
            )
        elif event_type == "weekly_focus_summary" and recipient_role in {"капитан", "captain"}:
            components.scheduler_service.send_weekly_focus_summary_to_captains(
                now=scheduled_at,
                flow_id=str(row.get("flow_id", "")).strip() or None,
                event_id=str(row.get("event_id", "")).strip(),
            )

    def _run_loop(self, components: RuntimeComponents) -> None:
        logger.info("scheduler runner started")
        while not self.stop_event.is_set():
            try:
                self.run_due_jobs_once(components)
            except Exception as exc:
                logger.exception("scheduler runner tick failed")
                _notify_scheduler_runner_error(components.notification_router, exc)
            self.stop_event.wait(self.check_interval_seconds)
        logger.info("scheduler runner stopped")

    def _run_scheduler_job(
        self,
        components: RuntimeComponents,
        job_type: str,
        *,
        scheduled_at: datetime,
    ) -> None:
        if job_type == "week_close":
            result = components.scheduler_service.close_week(now=scheduled_at)
            logger.info(
                "scheduler week close completed",
                extra={
                    "job_type": job_type,
                    "scheduled_at": scheduled_at.isoformat(),
                    "gray_created_count": result.gray_created_count,
                    "existing_count": result.existing_count,
                    "failed_count": result.failed_count,
                    "notified_team_count": result.notified_team_count,
                },
            )
            return

        if job_type == "weekly_focus_summary_captain":
            result = components.scheduler_service.send_weekly_focus_summary_to_captains(
                now=scheduled_at
            )
            logger.info(
                "scheduler weekly focus summary completed",
                extra={
                    "job_type": job_type,
                    "scheduled_at": scheduled_at.isoformat(),
                    "sent_count": result.sent_count,
                    "skipped_count": result.skipped_count,
                    "failed_count": result.failed_count,
                },
            )
            return

        result = components.scheduler_service.run_reminder(job_type, now=scheduled_at)
        logger.info(
            "scheduler reminder completed",
            extra={
                "job_type": job_type,
                "scheduled_at": scheduled_at.isoformat(),
                "sent_count": result.sent_count,
                "skipped_count": result.skipped_count,
                "failed_count": result.failed_count,
            },
        )

    def _now(self) -> datetime:
        if self.now_provider is not None:
            return self.now_provider()
        return datetime.now(ZoneInfo(TIMEZONE_NAME))


def _flow_event_scheduled_at(row: dict[str, object]) -> datetime | None:
    if str(row.get("scheduled_timezone", "")).strip() != TIMEZONE_NAME:
        return None
    raw_date = str(row.get("scheduled_date", "")).strip()
    raw_time = str(row.get("scheduled_time", "")).strip()
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        try:
            parsed_date = datetime.strptime(raw_date, "%d.%m.%Y").date()
        except ValueError:
            return None
    try:
        parsed_time = time.fromisoformat(raw_time)
    except ValueError:
        return None
    return datetime.combine(parsed_date, parsed_time, tzinfo=ZoneInfo(TIMEZONE_NAME))


def _focus_reminder_type(row: dict[str, object]) -> str:
    raw_time = str(row.get("scheduled_time", "")).strip()
    if raw_time.startswith("13:"):
        return "monday_focus_1300"
    if raw_time.startswith("19:"):
        return "monday_focus_1900"
    return "monday_reminder"


def _is_valid_focus_schedule_row(row: dict[str, object]) -> bool:
    event_type = str(row.get("event_type", "")).strip()
    recipient = str(row.get("recipient_role", "")).strip().lower()
    if str(row.get("scheduled_timezone", "")).strip() != TIMEZONE_NAME:
        return False
    if _flow_event_scheduled_at(row) is None or not str(row.get("event_id", "")).strip():
        return False
    return (
        event_type == "weekly_focus_prompt" and recipient in {"участник", "participant"}
    ) or (
        event_type == "weekly_focus_summary" and recipient in {"капитан", "captain"}
    )


def run_bot(
    settings: Settings,
    *,
    components_factory: RuntimeComponentsFactory | None = None,
    polling_runner: PollingRunner | None = None,
    scheduler_runner: SchedulerRunner | None = None,
    google_service_factory: GoogleServiceFactory | None = None,
) -> None:
    """Run the live Telegram polling runtime."""

    configure_challenge_calendar(start_date=settings.challenge.start_date)
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
    register_main_bot_commands(components)
    scheduler_started = False
    if polling_runner is None:
        stop_event = Event()
        _install_shutdown_handlers(stop_event)
        polling_runner = TelegramPollingRunner(
            poll_timeout_seconds=settings.telegram_runtime.poll_timeout_seconds,
            poll_limit=settings.telegram_runtime.poll_limit,
            stop_event=stop_event,
        )
        if scheduler_runner is None:
            scheduler_runner = LiveSchedulerRunner(stop_event=stop_event)

    try:
        if scheduler_runner is not None:
            scheduler_runner.start(components)
            scheduler_started = True
        polling_runner.run(components)
    finally:
        if scheduler_started:
            scheduler_runner.stop()


def register_main_bot_commands(components: RuntimeComponents) -> None:
    components.main_bot.set_commands(
        (
            BotCommand("start", "Главное меню"),
            BotCommand("menu", "Показать меню"),
        )
    )


def _last_scheduled_at(item: ScheduleItem, local_now: datetime) -> datetime | None:
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=ZoneInfo(TIMEZONE_NAME))
    else:
        local_now = local_now.astimezone(ZoneInfo(TIMEZONE_NAME))

    days_since_run_day = (local_now.weekday() - item.weekday) % 7
    scheduled_date = local_now.date() - timedelta(days=days_since_run_day)
    scheduled_at = datetime.combine(
        scheduled_date,
        item.run_at,
        tzinfo=ZoneInfo(TIMEZONE_NAME),
    )
    if scheduled_at > local_now:
        return None
    return scheduled_at


def _notify_scheduler_runner_error(router: NotificationRouter, error: Exception) -> None:
    try:
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=f"scheduler_runner_tick_failed error_type={type(error).__name__}",
            recipients=(),
        )
    except Exception as notify_error:
        logger.exception(
            "failed to notify scheduler runner error",
            extra={
                "error_type": type(error).__name__,
                "notify_error_type": type(notify_error).__name__,
            },
        )


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
        configure_challenge_calendar(start_date=settings.challenge.start_date)
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


def _configure_challenge_calendar_from_sheets(settings: Settings, gateway: GoogleSheetsGateway) -> None:
    flow = gateway.get_active_challenge_flow()
    if flow is None:
        configure_challenge_calendar(start_date=settings.challenge.start_date)
        return

    raw_start_date = flow.get("challenge_start_date")
    if raw_start_date is None or str(raw_start_date).strip() == "":
        raise ConfigurationError("Active ChallengeFlows.challenge_start_date is required")
    try:
        start_date = date.fromisoformat(str(raw_start_date).strip())
    except ValueError as exc:
        raise ConfigurationError("Active ChallengeFlows.challenge_start_date must be YYYY-MM-DD") from exc
    configure_challenge_calendar(start_date=start_date)


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
    try:
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=" ".join(parts),
            recipients=(),
        )
    except Exception as notify_error:
        logger.exception(
            "failed to notify polling error",
            extra={
                "event": event,
                "error_type": type(error).__name__,
                "notify_error_type": type(notify_error).__name__,
                "update_id": update_id,
            },
        )


def _install_shutdown_handlers(stop_event: Event) -> None:
    def _stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
