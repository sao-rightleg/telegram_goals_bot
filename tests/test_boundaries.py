import ast
from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.reports.generator import FakeReportGenerator, ReportRequest, ReportType
from app.services.notifications import (
    NotificationCategory,
    NotificationRouter,
    Recipient,
    RecipientType,
)
from app.sheets.gateway import FakeSheetsGateway
from app.speech.transcription import FakeSpeechTranscriber, TranscriptionRequest
from app.storage.paths import StoragePathPolicy


BOUNDARY_MODULES = [
    Path("app/sheets/gateway.py"),
    Path("app/bot/clients.py"),
    Path("app/services/notifications.py"),
    Path("app/reports/generator.py"),
    Path("app/speech/transcription.py"),
]


def test_sheets_fake_requires_no_credentials() -> None:
    gateway = FakeSheetsGateway()

    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001"})
    gateway.append_insight({"insight_id": "I001", "participant_id": "P001"})

    assert gateway.list_weekly_reports() == [
        {"weekly_report_id": "WR001", "participant_id": "P001"}
    ]
    assert gateway.list_insights() == [{"insight_id": "I001", "participant_id": "P001"}]


def test_three_bot_boundaries_are_distinct() -> None:
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)

    assert main_bot.purpose is BotPurpose.MAIN
    assert error_bot.purpose is BotPurpose.ERROR
    assert notification_bot.purpose is BotPurpose.NOTIFICATION
    assert len({main_bot.purpose, error_bot.purpose, notification_bot.purpose}) == 3


def test_technical_errors_route_only_to_error_bot() -> None:
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )

    router.send(
        category=NotificationCategory.TECHNICAL_ERROR,
        text="SQLite error",
        recipients=[
            Recipient(RecipientType.PARTICIPANT, "P001"),
            Recipient(RecipientType.CAPTAIN, "C001"),
        ],
    )

    assert main_bot.sent_messages == []
    assert notification_bot.sent_messages == []
    assert [message.chat_id for message in error_bot.sent_messages] == ["admin-errors"]


def test_operational_notifications_use_notification_bot() -> None:
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=FakeBotClient(BotPurpose.ERROR),
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )

    router.send(
        category=NotificationCategory.REPORT_DELIVERY,
        text="Weekly report",
        recipients=[Recipient(RecipientType.CAPTAIN, "C001")],
    )

    assert [message.chat_id for message in notification_bot.sent_messages] == ["C001"]


def test_report_and_speech_boundaries_are_importable() -> None:
    path_policy = StoragePathPolicy()
    report_generator = FakeReportGenerator(path_policy=path_policy)
    speech_transcriber = FakeSpeechTranscriber(transcription_text="transcribed")

    report = report_generator.generate_team_report(
        ReportRequest(report_type=ReportType.PDF_TEAM_REPORT, week_number=3, team_id="T001")
    )
    transcription = speech_transcriber.transcribe(
        TranscriptionRequest(audio_path=Path("data/audio/sample.ogg"), duration_seconds=30)
    )

    assert report.file_path == Path("reports/pdf/2026/week_03/T001/T001.pdf")
    assert transcription.text == "transcribed"


def test_boundary_modules_do_not_import_live_sdks() -> None:
    forbidden_roots = {
        "aiogram",
        "telegram",
        "google",
        "gspread",
        "reportlab",
        "weasyprint",
        "openai",
        "whisper",
    }

    for module_path in BOUNDARY_MODULES:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )

        assert imports.isdisjoint(forbidden_roots), module_path
