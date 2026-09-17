"""Production runtime readiness helpers and CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
import faulthandler
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
from app.bot.dispatch import TelegramUpdateDispatcher
from app.bot.rupor_dispatch import RuporUpdateDispatcher
from app.config import ConfigurationError, Settings, load_settings
from app.reports.delivery import ReportDeliveryService
from app.reports.pdf import LocalPdfRenderer
from app.reports.service import ReportService
from app.scheduler.calendar import (
    TIMEZONE_NAME,
    ScheduleItem,
    closed_challenge_week_count,
    is_working_week,
    reminder_schedule,
)
from app.scheduler.calendar import configure_challenge_calendar
from app.scheduler.jobs import SchedulerService
from app.services.captains import CaptainService
from app.services.insights import InsightService
from app.services.notifications import NotificationCategory, NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.rupor import RuporService
from app.services.voice_messages import VoiceMessageService
from app.services.weekly_reports import WeeklyReportService
from app.sheets.gateway import (
    GoogleSheetsError,
    GoogleSheetsGateway,
    SheetRow,
    validate_challenge_flows_schema,
    validate_required_schema,
)
from app.speech.transcription import FakeSpeechTranscriber, YandexSpeechKitTranscriber
from app.storage.dialog_state import DialogStateRepository
from app.storage.registration import RegistrationDraftRepository
from app.storage.rupor import RuporRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.goal_drafts import GoalDraftRepository
from app.storage.paths import StoragePathPolicy
from app.storage.reports import ReportStateRepository
from app.storage.scheduler import SchedulerJobRepository
from app.storage.sqlite import REQUIRED_TECHNICAL_TABLES, initialize_schema, list_tables
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


logger = logging.getLogger("telegram_goals_bot")

RUNTIME_FAILURE_ALERT_THRESHOLD = 3
RUNTIME_RETRY_BASE_SECONDS = 1.0
RUNTIME_RETRY_MAX_SECONDS = 10.0


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
    report_service: ReportService | None = None
    rupor_bot: LiveTelegramBotClient | None = None
    rupor_dispatcher: RuporUpdateDispatcher | None = None

    def with_replacements(self, **changes: object) -> "RuntimeComponents":
        return replace(self, **changes)


@dataclass(frozen=True)
class LiveBotSet:
    main: LiveTelegramBotClient
    error: LiveTelegramBotClient
    notification: LiveTelegramBotClient
    rupor: LiveTelegramBotClient | None


@dataclass(frozen=True)
class BoundFlowGateway:
    """In-memory flow binding used after one startup registry lookup."""

    flow: SheetRow

    def get_active_challenge_flow(self) -> SheetRow:
        return dict(self.flow)


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
            registry = GoogleSheetsGateway(
                service=google_service,
                spreadsheet_id=settings.google_sheets.challenge_flows_sheet_id,
            )
            bound_flow = _bound_flow_for_spreadsheet(registry, settings.google_sheets.sheet_id)
            _configure_challenge_calendar_from_sheets(settings, BoundFlowGateway(bound_flow))
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
    bots = _build_live_bots(settings)
    notification_router = NotificationRouter(
        main_bot=bots.main,
        error_bot=bots.error,
        notification_bot=bots.notification,
        admin_error_recipient=Recipient(
            RecipientType.ADMIN_ERROR_CHAT,
            str(settings.admin.admin_error_chat_id),
        ),
    )
    db_path = settings.storage.sqlite_db_path
    dialog_states = DialogStateRepository(db_path)
    registration_drafts = RegistrationDraftRepository(db_path)
    goal_drafts = GoalDraftRepository(db_path)
    weekly_drafts = WeeklyReportDraftRepository(db_path)
    insight_drafts = InsightDraftRepository(db_path)
    scheduler_jobs = SchedulerJobRepository(db_path)
    sheets_gateway, bound_flow = _build_sheets_and_flow(
        settings, selected_google_service_factory(settings)
    )
    bound_flow_gateway = BoundFlowGateway(bound_flow)
    _configure_challenge_calendar_from_sheets(settings, bound_flow_gateway)
    voice_service = _build_voice_service(
        settings, dialog_states, weekly_drafts, insight_drafts, notification_router
    )
    participant_service = ParticipantFlowService(
        sheets=sheets_gateway,
        main_bot=bots.main,
        notification_router=notification_router,
        dialog_states=dialog_states,
        registration_flows=bound_flow_gateway,
        registration_drafts=registration_drafts,
        goal_drafts=goal_drafts,
    )
    weekly_report_service = WeeklyReportService(
        sheets=sheets_gateway,
        main_bot=bots.main,
        notification_router=notification_router,
        drafts=weekly_drafts,
        voice_messages=voice_service,
    )
    insight_service = InsightService(
        sheets=sheets_gateway,
        main_bot=bots.main,
        notification_router=notification_router,
        drafts=insight_drafts,
        voice_messages=voice_service,
    )
    captain_service = CaptainService(
        sheets=sheets_gateway,
        main_bot=bots.main,
        notification_router=notification_router,
        drafts=weekly_drafts,
    )
    scheduler_service = SchedulerService(
        sheets=sheets_gateway,
        notification_router=notification_router,
        repository=scheduler_jobs,
        admin_telegram_id=settings.admin.admin_telegram_id,
        sitnikov_telegram_id=settings.admin.sitnikov_telegram_id,
    )
    report_service = _build_report_service(
        settings, sheets_gateway, notification_router, bound_flow
    )
    dispatcher = TelegramUpdateDispatcher(
        participant_service=participant_service,
        weekly_report_service=weekly_report_service,
        insight_service=insight_service,
        captain_service=captain_service,
        dialog_states=dialog_states,
        notification_router=notification_router,
    )
    rupor_dispatcher = _build_rupor_dispatcher(
        settings, sheets_gateway, bots, notification_router
    )
    return RuntimeComponents(
        main_bot=bots.main,
        error_bot=bots.error,
        notification_bot=bots.notification,
        notification_router=notification_router,
        dispatcher=dispatcher,
        participant_service=participant_service,
        weekly_report_service=weekly_report_service,
        insight_service=insight_service,
        captain_service=captain_service,
        sheets_gateway=sheets_gateway,
        voice_service=voice_service,
        scheduler_service=scheduler_service,
        report_service=report_service,
        rupor_bot=bots.rupor,
        rupor_dispatcher=rupor_dispatcher,
    )


def _build_sheets_and_flow(
    settings: Settings, google_service: object
) -> tuple[GoogleSheetsGateway, SheetRow]:
    sheets = GoogleSheetsGateway(
        service=google_service, spreadsheet_id=settings.google_sheets.sheet_id
    )
    registry = GoogleSheetsGateway(
        service=google_service,
        spreadsheet_id=settings.google_sheets.challenge_flows_sheet_id,
    )
    return sheets, _bound_flow_for_spreadsheet(registry, settings.google_sheets.sheet_id)


def _build_live_bots(settings: Settings) -> LiveBotSet:
    timeout = settings.telegram_runtime.request_timeout_seconds
    main = LiveTelegramBotClient(
        purpose=BotPurpose.MAIN,
        token=_required_token(settings.telegram.main_bot_token, "MAIN_TELEGRAM_BOT_TOKEN"),
        http_client=httpx.Client(timeout=timeout),
    )
    error = LiveTelegramBotClient(
        purpose=BotPurpose.ERROR,
        token=_required_token(settings.telegram.error_bot_token, "ERROR_TELEGRAM_BOT_TOKEN"),
        http_client=httpx.Client(timeout=timeout),
    )
    notification = LiveTelegramBotClient(
        purpose=BotPurpose.NOTIFICATION,
        token=_required_token(
            settings.telegram.notification_bot_token, "NOTIFICATION_TELEGRAM_BOT_TOKEN"
        ),
        http_client=httpx.Client(timeout=timeout),
    )
    rupor = None
    if settings.rupor.enabled:
        rupor = LiveTelegramBotClient(
            purpose=BotPurpose.RUPOR,
            token=_required_token(settings.rupor.bot_token, "RUPOR_TELEGRAM_BOT_TOKEN"),
            http_client=httpx.Client(timeout=timeout),
        )
    return LiveBotSet(main=main, error=error, notification=notification, rupor=rupor)


def _build_voice_service(
    settings: Settings,
    dialog_states: DialogStateRepository,
    weekly_drafts: WeeklyReportDraftRepository,
    insight_drafts: InsightDraftRepository,
    notification_router: NotificationRouter,
) -> VoiceMessageService:
    return VoiceMessageService(
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
            http_client=httpx.Client(timeout=settings.telegram_runtime.request_timeout_seconds),
        ),
        transcriber=_build_transcriber(settings, http_client=httpx.Client()),
        notification_router=notification_router,
    )


def _build_report_service(
    settings: Settings,
    sheets_gateway: GoogleSheetsGateway,
    notification_router: NotificationRouter,
    bound_flow: SheetRow,
) -> ReportService:
    repository = ReportStateRepository(settings.storage.sqlite_db_path)
    return ReportService(
        sheets_gateway=sheets_gateway,
        report_repository=repository,
        pdf_renderer=LocalPdfRenderer(StoragePathPolicy(pdf_root=settings.storage.pdf_storage_dir)),
        delivery_service=ReportDeliveryService(
            repository=repository, notification_router=notification_router
        ),
        flow_id=str(bound_flow.get("flow_id", "")).strip(),
        flow_name=str(bound_flow.get("flow_name", "")).strip() or None,
        admin_telegram_id=settings.admin.admin_telegram_id,
        sitnikov_telegram_id=settings.admin.sitnikov_telegram_id,
    )


def _build_rupor_dispatcher(
    settings: Settings,
    sheets_gateway: GoogleSheetsGateway,
    bots: LiveBotSet,
    notification_router: NotificationRouter,
) -> RuporUpdateDispatcher | None:
    if bots.rupor is None:
        return None
    service = RuporService(
        sheets=sheets_gateway,
        rupor_bot=bots.rupor,
        delivery_bot=bots.main,
        notification_router=notification_router,
        repository=RuporRepository(settings.storage.sqlite_db_path),
        allowed_telegram_ids=frozenset(settings.rupor.allowed_telegram_ids),
        delivery_pause_seconds=settings.rupor.delivery_pause_seconds,
    )
    return RuporUpdateDispatcher(service=service)


@dataclass
class TelegramPollingRunner:
    poll_timeout_seconds: int
    poll_limit: int
    stop_event: Event

    def run(self, components: RuntimeComponents) -> None:
        offset: int | None = None
        consecutive_failures = 0
        failure_alerted = False
        while not self.stop_event.is_set():
            try:
                updates = components.main_bot.get_updates(
                    offset=offset,
                    timeout_seconds=self.poll_timeout_seconds,
                    limit=self.poll_limit,
                )
            except Exception as exc:
                consecutive_failures += 1
                if consecutive_failures >= RUNTIME_FAILURE_ALERT_THRESHOLD and not failure_alerted:
                    failure_alerted = _notify_polling_error(
                        components.notification_router,
                        event="telegram_get_updates_failed",
                        error=exc,
                        consecutive_failures=consecutive_failures,
                    )
                retry_delay = min(
                    RUNTIME_RETRY_BASE_SECONDS * (2 ** (consecutive_failures - 1)),
                    RUNTIME_RETRY_MAX_SECONDS,
                )
                self.stop_event.wait(retry_delay)
                continue

            if failure_alerted:
                recovery_sent = _notify_runtime_recovery(
                    components.notification_router,
                    event="telegram_get_updates_recovered",
                )
            consecutive_failures = 0
            failure_alerted = failure_alerted and not recovery_sent

            for update in updates:
                offset = self._process_update(components, update, current_offset=offset)

    def _process_update(
        self,
        components: RuntimeComponents,
        update: dict[str, object],
        *,
        current_offset: int | None,
    ) -> int | None:
        update_id = update.get("update_id")
        normalized_update_id = update_id if isinstance(update_id, int) else None
        callback_query_id, callback_chat_id = _callback_context(update)
        if callback_query_id is not None:
            self._ack_callback(components, callback_query_id, update_id=normalized_update_id)
        try:
            components.dispatcher.dispatch_update(update)
        except Exception as exc:
            _notify_polling_error(
                components.notification_router,
                event="telegram_update_dispatch_failed",
                error=exc,
                update_id=normalized_update_id,
            )
            if callback_chat_id is not None:
                self._reply_callback_error(
                    components,
                    callback_chat_id,
                    update_id=normalized_update_id,
                )
        return normalized_update_id + 1 if normalized_update_id is not None else current_offset

    @staticmethod
    def _ack_callback(
        components: RuntimeComponents, callback_query_id: str, *, update_id: int | None
    ) -> None:
        try:
            components.main_bot.answer_callback_query(callback_query_id)
        except Exception as exc:
            _notify_polling_error(
                components.notification_router,
                event="telegram_callback_ack_failed",
                error=exc,
                update_id=update_id,
            )

    @staticmethod
    def _reply_callback_error(
        components: RuntimeComponents, callback_chat_id: str, *, update_id: int | None
    ) -> None:
        support_code = str(update_id) if update_id is not None else "unknown"
        try:
            components.main_bot.send_message(
                chat_id=callback_chat_id,
                text=(
                    "Не удалось обработать нажатие. Попробуй ещё раз или отправь /start. "
                    f"Код обращения: {support_code}."
                ),
            )
        except Exception as exc:
            _notify_polling_error(
                components.notification_router,
                event="telegram_callback_error_reply_failed",
                error=exc,
                update_id=update_id,
            )


@dataclass
class RuporPollingRunner:
    poll_timeout_seconds: int
    poll_limit: int
    stop_event: Event

    def run(self, components: RuntimeComponents) -> None:
        if components.rupor_bot is None or components.rupor_dispatcher is None:
            return
        try:
            components.rupor_dispatcher.resume_incomplete()
        except Exception as exc:
            _notify_polling_error(
                components.notification_router,
                event="rupor_startup_recovery_failed",
                error=exc,
            )
        offset: int | None = None
        while not self.stop_event.is_set():
            try:
                updates = components.rupor_bot.get_updates(
                    offset=offset,
                    timeout_seconds=self.poll_timeout_seconds,
                    limit=self.poll_limit,
                )
                for update in updates:
                    update_id = update.get("update_id")
                    callback_query_id, _chat_id = _callback_context(update)
                    try:
                        if callback_query_id is not None:
                            components.rupor_bot.answer_callback_query(callback_query_id)
                        components.rupor_dispatcher.dispatch_update(update)
                    except Exception as exc:
                        _notify_polling_error(
                            components.notification_router,
                            event="rupor_update_dispatch_failed",
                            error=exc,
                            update_id=update_id if isinstance(update_id, int) else None,
                        )
                    finally:
                        if isinstance(update_id, int):
                            offset = update_id + 1
            except Exception as exc:
                _notify_polling_error(
                    components.notification_router,
                    event="rupor_polling_failed",
                    error=exc,
                )
                self.stop_event.wait(RUNTIME_RETRY_BASE_SECONDS)

def _callback_context(update: dict[str, object]) -> tuple[str | None, str | None]:
    callback = update.get("callback_query")
    if not isinstance(callback, dict):
        return None, None
    callback_id = callback.get("id")
    message = callback.get("message")
    chat = message.get("chat") if isinstance(message, dict) else None
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    return (
        str(callback_id) if isinstance(callback_id, (str, int)) else None,
        str(chat_id) if isinstance(chat_id, (str, int)) else None,
    )


@dataclass
class LiveSchedulerRunner:
    stop_event: Event
    check_interval_seconds: float = 30.0
    catch_up_window: timedelta = timedelta(minutes=15)
    now_provider: Callable[[], datetime] | None = None

    def __post_init__(self) -> None:
        self._thread: Thread | None = None
        self._dispatched_keys: set[str] = set()
        self._consecutive_tick_failures = 0
        self._tick_failure_alerted = False

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
            self._run_flow_schedule_event(components, row, scheduled_at=scheduled_at)
            self._dispatched_keys.add(dispatch_key)

        for item in reminder_schedule():
            scheduled_at = _last_scheduled_at(item, local_current)
            if scheduled_at is None:
                continue
            if _has_matching_dynamic_focus_event(
                schedule_rows,
                job_type=item.job_type,
                scheduled_at=scheduled_at,
            ):
                continue
            catch_up_window = (
                timedelta(hours=1)
                if item.job_type in {"week_close", "weekly_reports"}
                else self.catch_up_window
            )
            if local_current - scheduled_at > catch_up_window:
                continue

            dispatch_key = f"{item.job_type}:{scheduled_at.isoformat()}"
            if dispatch_key in self._dispatched_keys:
                continue

            self._run_scheduler_job(components, item.job_type, scheduled_at=scheduled_at)
            self._dispatched_keys.add(dispatch_key)

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
        elif event_type == "participant_message" and recipient_role in {"участник", "participant"}:
            flow_id = str(row.get("flow_id", "")).strip()
            event_id = str(row.get("event_id", "")).strip()
            message_text = str(row.get("message_text", "")).strip()
            attachment_url = str(row.get("attachment_url", "")).strip() or None
            condition = str(row.get("condition_code", "")).strip()
            if not flow_id or not event_id or not message_text or condition not in {
                "goal_missing",
                "steps_missing",
            }:
                return
            if attachment_url and (condition != "goal_missing" or not event_id.startswith("GOAL_START")):
                return
            result = components.scheduler_service.send_scheduled_participant_message(
                text=message_text,
                condition=condition,
                attachment_url=attachment_url,
                now=scheduled_at,
                flow_id=flow_id,
                event_id=event_id,
            )
            if result.failed_count:
                raise RuntimeError("scheduled participant message incomplete")
        elif event_type == "setup_progress_summary":
            flow_id = str(row.get("flow_id", "")).strip()
            event_id = str(row.get("event_id", "")).strip()
            message_text = str(row.get("message_text", "")).strip()
            if not flow_id or not event_id or not message_text or recipient_role not in {
                "капитан", "captain", "трекер", "tracker", "администратор", "admin", "ситников", "sitnikov"
            }:
                return
            result = components.scheduler_service.send_steps_setup_summary(
                template=message_text,
                recipient_role=recipient_role,
                now=scheduled_at,
                flow_id=flow_id,
                event_id=event_id,
            )
            if result.failed_count:
                raise RuntimeError("steps setup summary incomplete")
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
                self._consecutive_tick_failures += 1
                if (
                    self._consecutive_tick_failures >= RUNTIME_FAILURE_ALERT_THRESHOLD
                    and not self._tick_failure_alerted
                ):
                    self._tick_failure_alerted = _notify_scheduler_runner_error(
                        components.notification_router,
                        exc,
                        consecutive_failures=self._consecutive_tick_failures,
                    )
            else:
                if self._tick_failure_alerted:
                    recovery_sent = _notify_runtime_recovery(
                        components.notification_router,
                        event="scheduler_runner_recovered",
                    )
                    self._tick_failure_alerted = not recovery_sent
                self._consecutive_tick_failures = 0
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

        if job_type == "weekly_reports":
            if not is_working_week(scheduled_at - timedelta(days=1)):
                return
            week_number = closed_challenge_week_count(scheduled_at)
            if week_number == 0 or components.report_service is None:
                return
            result = components.report_service.generate_and_send_week(
                week_number,
                now=scheduled_at,
            )
            if result.failed_count:
                raise RuntimeError("weekly report generation or delivery incomplete")
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
    if row.get("is_enabled") is not True:
        return False
    if str(row.get("scheduled_timezone", "")).strip() != TIMEZONE_NAME:
        return False
    if _flow_event_scheduled_at(row) is None or not str(row.get("event_id", "")).strip():
        return False
    return (
        event_type == "weekly_focus_prompt" and recipient in {"участник", "participant"}
    ) or (
        event_type == "weekly_focus_summary" and recipient in {"капитан", "captain"}
    )


def _has_matching_dynamic_focus_event(
    rows: Sequence[dict[str, object]],
    *,
    job_type: str,
    scheduled_at: datetime,
) -> bool:
    for row in rows:
        if not _is_valid_focus_schedule_row(row):
            continue
        if _flow_event_scheduled_at(row) != scheduled_at:
            continue
        event_type = str(row.get("event_type", "")).strip()
        dynamic_job_type = (
            "weekly_focus_summary_captain"
            if event_type == "weekly_focus_summary"
            else _focus_reminder_type(row)
        )
        if dynamic_job_type == job_type:
            return True
    return False


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
        def components_factory(runtime_settings: Settings) -> RuntimeComponents:
            return compose_runtime(
                runtime_settings,
                google_service_factory=google_service_factory,
            )

    components = components_factory(settings)
    register_main_bot_commands(components)
    scheduler_started = False
    rupor_thread: Thread | None = None
    if polling_runner is None:
        polling_runner, scheduler_runner, rupor_thread = _create_default_runners(
            settings, components, scheduler_runner=scheduler_runner
        )

    try:
        if scheduler_runner is not None:
            scheduler_runner.start(components)
            scheduler_started = True
        polling_runner.run(components)
    finally:
        if scheduler_started:
            scheduler_runner.stop()
        if rupor_thread is not None:
            rupor_thread.join(timeout=settings.telegram_runtime.poll_timeout_seconds + 2)


def _create_default_runners(
    settings: Settings,
    components: RuntimeComponents,
    *,
    scheduler_runner: SchedulerRunner | None,
) -> tuple[PollingRunner, SchedulerRunner, Thread | None]:
    stop_event = Event()
    _install_shutdown_handlers(stop_event)
    polling = TelegramPollingRunner(
        poll_timeout_seconds=settings.telegram_runtime.poll_timeout_seconds,
        poll_limit=settings.telegram_runtime.poll_limit,
        stop_event=stop_event,
    )
    scheduler = scheduler_runner or LiveSchedulerRunner(stop_event=stop_event)
    rupor_thread = None
    if components.rupor_bot is not None and components.rupor_dispatcher is not None:
        rupor = RuporPollingRunner(
            poll_timeout_seconds=settings.telegram_runtime.poll_timeout_seconds,
            poll_limit=settings.telegram_runtime.poll_limit,
            stop_event=stop_event,
        )
        rupor_thread = Thread(
            target=rupor.run,
            args=(components,),
            name="rupor-polling",
            daemon=True,
        )
        rupor_thread.start()
    return polling, scheduler, rupor_thread


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


def _notify_scheduler_runner_error(
    router: NotificationRouter,
    error: Exception,
    *,
    consecutive_failures: int,
) -> bool:
    try:
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=(
                f"scheduler_runner_tick_failed error_type={type(error).__name__} "
                f"consecutive_failures={consecutive_failures}"
            ),
            recipients=(),
        )
        return True
    except Exception as notify_error:
        logger.exception(
            "failed to notify scheduler runner error",
            extra={
                "error_type": type(error).__name__,
                "notify_error_type": type(notify_error).__name__,
            },
        )
        return False


def main(
    argv: Sequence[str] | None = None,
    *,
    google_service_factory: GoogleServiceFactory | None = None,
) -> int:
    _enable_crash_diagnostics()
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


def _enable_crash_diagnostics() -> None:
    """Write native crash tracebacks to stderr, which systemd keeps in journal."""
    try:
        faulthandler.enable(all_threads=True)
    except (OSError, RuntimeError):
        logger.warning("native crash diagnostics could not be enabled")


def create_google_sheets_service(settings: Settings) -> object:
    import httplib2
    from google_auth_httplib2 import AuthorizedHttp
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    credentials = Credentials.from_service_account_file(
        str(settings.google_sheets.application_credentials),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    authorized_http = AuthorizedHttp(credentials, http=httplib2.Http(timeout=5.0))
    return build("sheets", "v4", http=authorized_http, cache_discovery=False)


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


def _bound_flow_for_spreadsheet(
    registry: GoogleSheetsGateway,
    spreadsheet_id: str,
) -> SheetRow:
    rows = registry.list_challenge_flows()
    explicit = [
        row for row in rows
        if str(row.get("flow_spreadsheet_id", "")).strip() == spreadsheet_id
    ]
    active = [
        row for row in explicit
        if str(row.get("flow_status", "")).strip().lower() == "active"
    ]
    if len(active) != 1:
        raise ConfigurationError("Configured spreadsheet must have exactly one active flow")
    return dict(active[0])


def _configure_challenge_calendar_from_sheets(
    settings: Settings,
    gateway: GoogleSheetsGateway | BoundFlowGateway,
) -> None:
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
    raw_working_start_date = flow.get("week_01_start_date")
    if raw_working_start_date is None or str(raw_working_start_date).strip() == "":
        raise ConfigurationError("Active ChallengeFlows.week_01_start_date is required")
    try:
        working_start_date = date.fromisoformat(str(raw_working_start_date).strip())
    except ValueError as exc:
        raise ConfigurationError(
            "Active ChallengeFlows.week_01_start_date must be YYYY-MM-DD"
        ) from exc
    try:
        configure_challenge_calendar(
            start_date=start_date,
            working_start_date=working_start_date,
        )
    except ValueError as exc:
        raise ConfigurationError("Active challenge flow calendar is inconsistent") from exc


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
    consecutive_failures: int | None = None,
) -> bool:
    parts = [event, f"error_type={type(error).__name__}"]
    if update_id is not None:
        parts.append(f"update_id={update_id}")
    if consecutive_failures is not None:
        parts.append(f"consecutive_failures={consecutive_failures}")
    try:
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=" ".join(parts),
            recipients=(),
        )
        return True
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
        return False


def _notify_runtime_recovery(router: NotificationRouter, *, event: str) -> bool:
    try:
        router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=event,
            recipients=(),
        )
        return True
    except Exception as notify_error:
        logger.exception(
            "failed to notify runtime recovery",
            extra={"event": event, "notify_error_type": type(notify_error).__name__},
        )
        return False


def _install_shutdown_handlers(stop_event: Event) -> None:
    def _stop(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
