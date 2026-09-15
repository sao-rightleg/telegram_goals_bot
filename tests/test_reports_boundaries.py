from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient, OutgoingMessage
from app.reports.aggregation import build_all_teams_report
from app.reports.delivery import ReportDeliveryPlan, ReportDeliveryPlanner, ReportDeliveryService
from app.reports.models import (
    AllTeamsReportData,
    ReportDeliveryItem,
    ReportRecipient,
    ReportType,
    TeamReportData,
)
from app.reports.pdf import LocalPdfRenderer
from app.reports.service import ReportService
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import FakeSheetsGateway
from app.storage.paths import StoragePathPolicy
from app.storage.reports import ReportStateRepository
from app.storage.sqlite import initialize_schema


NOW = datetime(2026, 7, 12, 23, 59, tzinfo=ZoneInfo(TIMEZONE_NAME))


def test_captain_and_tracker_outputs_do_not_include_group_comparison() -> None:
    plan = ReportDeliveryPlanner(
        team_summary_texts={"T001": "team summary"},
        team_pdf_paths={"T001": Path("/tmp/T001.pdf")},
        tracker_summary_texts={"TR001": "tracker summary"},
        tracker_pdf_paths={"TR001": Path("/tmp/TR001.pdf")},
    ).build_plan(
        _report_data(),
        participants=[
            {"participant_id": "C001", "role": "captain", "team_id": "T001", "telegram_id": 2001},
        ],
        teams=[{"team_id": "T001", "gender": "male", "captain_id": "C001"}],
        trackers=[{"tracker_id": "TR001", "telegram_id": 3001, "gender_scope": "male", "is_active": True}],
    )

    restricted_items = [
        item
        for item in plan.items
        if item.recipient.recipient_type in {"captain", "tracker"}
    ]
    assert restricted_items
    assert all(item.report_type is not ReportType.GROUP_COMPARISON for item in restricted_items)


def test_admin_error_messages_do_not_include_report_body_or_secrets(tmp_path: Path) -> None:
    service, _repository, error_bot, _notification_bot = _delivery_service(
        tmp_path,
        notification_bot=AlwaysFailingBot(BotPurpose.NOTIFICATION),
    )
    plan = ReportDeliveryPlan(
        items=[
            ReportDeliveryItem(
                report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                scope_id="T001",
                recipient=ReportRecipient("captain", "C001", "2001", "T001"),
                text="личный отчёт участника token=secret",
            )
        ]
    )

    service.deliver_plan(week_number=5, plan=plan, sent_at=NOW.isoformat())

    error_text = error_bot.sent_messages[0].text
    assert "token=secret" not in error_text
    assert "личный отчёт" not in error_text
    assert "telegram_team_summary" in error_text


def test_report_rerun_does_not_duplicate_successful_delivery_items(tmp_path: Path) -> None:
    service, _repository, _error_bot, notification_bot = _report_service(tmp_path)

    first = service.generate_and_send_week(5, now=NOW)
    sent_messages_after_first = len(notification_bot.sent_messages)
    sent_documents_after_first = len(notification_bot.sent_documents)
    second = service.generate_and_send_week(5, now=NOW)

    assert first.sent_count > 0
    assert second.skipped_count == first.sent_count
    assert len(notification_bot.sent_messages) == sent_messages_after_first
    assert len(notification_bot.sent_documents) == sent_documents_after_first


def test_generated_report_artifacts_are_not_written_inside_repo_during_tests() -> None:
    repo_pdf_root = Path("reports/pdf")

    generated_pdfs = list(repo_pdf_root.rglob("*.pdf")) if repo_pdf_root.exists() else []

    assert generated_pdfs == []


def test_deleted_audio_file_path_does_not_break_reports() -> None:
    gateway = _gateway(
        weekly_reports=[
            {
                "weekly_report_id": "WR001",
                "participant_id": "P001",
                "team_id": "T001",
                "goal_id": "G001",
                "week_number": 5,
                "status_code": "green",
                "status_symbol": "🟩",
                "status_score": 1,
                "report_text": "Текст отчёта",
                "transcription_text": "Расшифровка сохранена",
                "audio_file_path": "/tmp/deleted-audio.ogg",
                "audio_deleted_at": "2026-07-15T10:00:00+05:00",
            }
        ]
    )

    report = build_all_teams_report(gateway, week_number=5)

    assert report.teams[0].participants[0].transcription_text == "Расшифровка сохранена"


def test_report_generation_ignores_unfinished_sqlite_drafts(tmp_path: Path) -> None:
    service, _repository, _error_bot, notification_bot = _report_service(
        tmp_path,
        sheets_gateway=_gateway(weekly_reports=[]),
    )

    service.generate_and_send_week(5, now=NOW)

    rendered_text = "\n".join(message.text for message in notification_bot.sent_messages)
    assert "черновик" not in rendered_text.lower()
    assert "draft" not in rendered_text.lower()


def _report_data() -> AllTeamsReportData:
    return AllTeamsReportData(
        week_number=5,
        total_active_count=1,
        total_dropped_count=0,
        average_victory_percent=100,
        teams=(
            TeamReportData(
                week_number=5,
                team_id="T001",
                team_name="Команда А",
                captain_id="C001",
                captain_name="Капитан",
                active_count=1,
                dropped_count=0,
                status_distribution={"green": 1, "blue": 0, "red": 0, "gray": 0},
                weekly_victory_percent=100,
                participants=(),
            ),
        ),
    )


def _report_service(
    tmp_path: Path,
    *,
    sheets_gateway: FakeSheetsGateway | None = None,
) -> tuple[ReportService, ReportStateRepository, FakeBotClient, FakeBotClient]:
    repository, router, error_bot, notification_bot = _router_and_repository(tmp_path)
    service = ReportService(
        sheets_gateway=sheets_gateway or _gateway(),
        report_repository=repository,
        pdf_renderer=LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf")),
        delivery_service=ReportDeliveryService(repository=repository, notification_router=router),
        flow_id="FLOW_TEST",
    )
    return service, repository, error_bot, notification_bot


def _delivery_service(
    tmp_path: Path,
    *,
    notification_bot: FakeBotClient,
) -> tuple[ReportDeliveryService, ReportStateRepository, FakeBotClient, FakeBotClient]:
    repository, router, error_bot, selected_notification_bot = _router_and_repository(
        tmp_path,
        notification_bot=notification_bot,
    )
    return (
        ReportDeliveryService(repository=repository, notification_router=router),
        repository,
        error_bot,
        selected_notification_bot,
    )


def _router_and_repository(
    tmp_path: Path,
    *,
    notification_bot: FakeBotClient | None = None,
) -> tuple[ReportStateRepository, NotificationRouter, FakeBotClient, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    selected_notification_bot = notification_bot or FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=selected_notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return repository, router, error_bot, selected_notification_bot


def _gateway(*, weekly_reports: list[dict[str, object]] | None = None) -> FakeSheetsGateway:
    return FakeSheetsGateway(
        teams=[{"team_id": "T001", "team_name": "Команда А", "gender": "male", "captain_id": "C001"}],
        participants=[
            {"participant_id": "P001", "role": "participant", "team_id": "T001", "full_name": "Анна", "status": "active"},
            {"participant_id": "C001", "role": "captain", "team_id": "T001", "full_name": "Капитан", "status": "active", "telegram_id": 2001},
            {"participant_id": "A001", "role": "admin", "full_name": "Админ", "status": "active", "telegram_id": 9001},
        ],
        goals=[
            {
                "goal_id": "G001",
                "participant_id": "P001",
                "goal_title": "Цель",
                "goal_description": "Описание",
                "goal_value_amount": "100000",
                "goal_value_currency": "RUB",
                "permission_condition": "Готово",
                "goal_status": "active",
            }
        ],
        planned_steps=[
            {"step_id": "S001", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Шаг", "step_status": "closed"},
        ],
        weekly_reports=weekly_reports
        if weekly_reports is not None
        else [
            {
                "weekly_report_id": "WR001",
                "participant_id": "P001",
                "team_id": "T001",
                "goal_id": "G001",
                "week_number": 5,
                "status_code": "green",
                "status_symbol": "🟩",
                "status_score": 1,
                "report_text": "Текст отчёта",
                "transcription_text": "Расшифровка",
            }
        ],
    )


class AlwaysFailingBot(FakeBotClient):
    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        raise RuntimeError("telegram token=secret unavailable")
