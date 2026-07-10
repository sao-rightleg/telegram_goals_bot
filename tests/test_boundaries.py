import ast
from pathlib import Path

import httpx
import pytest

from app.bot.clients import (
    BotPurpose,
    FakeBotClient,
    FakeTelegramFileDownloader,
    LiveTelegramBotClient,
    LiveTelegramFileDownloader,
    TelegramApiError,
    TelegramFileDownload,
)
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


def test_fake_telegram_file_downloader_writes_requested_local_file(tmp_path: Path) -> None:
    downloader = FakeTelegramFileDownloader()
    destination = tmp_path / "data" / "audio" / "voice.ogg"

    result = downloader.download_file(
        TelegramFileDownload(telegram_file_id="telegram-file-1", destination_path=destination)
    )

    assert result == destination
    assert destination.read_bytes() == b"fake telegram voice file: telegram-file-1"
    assert downloader.downloads == [
        TelegramFileDownload(telegram_file_id="telegram-file-1", destination_path=destination)
    ]


def test_live_telegram_client_sends_message_request() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 77}})

    client = LiveTelegramBotClient(
        purpose=BotPurpose.MAIN,
        token="secret-token-123",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    message = client.send_message(chat_id="1001", text="Привет")

    assert message.chat_id == "1001"
    assert message.text == "Привет"
    assert len(requests) == 1
    assert requests[0].url.path == "/botsecret-token-123/sendMessage"
    assert requests[0].read().decode("utf-8") == "chat_id=1001&text=%D0%9F%D1%80%D0%B8%D0%B2%D0%B5%D1%82"


def test_live_telegram_client_sends_document_request(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    document_path = tmp_path / "report.pdf"
    document_path.write_bytes(b"pdf bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = request.read()
        assert b"name=\"chat_id\"" in body
        assert b"1001" in body
        assert b"name=\"caption\"" in body
        assert b"Report" in body
        assert b'name="document"; filename="report.pdf"' in body
        assert b"pdf bytes" in body
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 78}})

    client = LiveTelegramBotClient(
        purpose=BotPurpose.NOTIFICATION,
        token="document-token-123",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    document = client.send_document(chat_id="1001", file_path=document_path, caption="Report")

    assert document.chat_id == "1001"
    assert document.file_path == document_path
    assert document.caption == "Report"
    assert requests[0].url.path == "/botdocument-token-123/sendDocument"


def test_live_telegram_file_downloader_writes_requested_path(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []
    destination = tmp_path / "audio" / "voice.ogg"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/getFile"):
            return httpx.Response(
                200,
                json={"ok": True, "result": {"file_path": "voice/file_123.ogg"}},
            )
        if request.url.path == "/file/botdownload-token-123/voice/file_123.ogg":
            return httpx.Response(200, content=b"voice bytes")
        return httpx.Response(404, json={"ok": False, "description": "not found"})

    downloader = LiveTelegramFileDownloader(
        token="download-token-123",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    result = downloader.download_file(
        TelegramFileDownload(
            telegram_file_id="telegram-file-1",
            destination_path=destination,
        )
    )

    assert result == destination
    assert destination.read_bytes() == b"voice bytes"
    assert [request.url.path for request in requests] == [
        "/botdownload-token-123/getFile",
        "/file/botdownload-token-123/voice/file_123.ogg",
    ]


def test_live_telegram_errors_are_sanitized() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": False, "description": "bad secret-token-123 request"},
        )

    client = LiveTelegramBotClient(
        purpose=BotPurpose.ERROR,
        token="secret-token-123",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(TelegramApiError) as error:
        client.send_message(chat_id="1001", text="test")

    message = str(error.value)
    assert "sendMessage" in message
    assert "secret-token-123" not in message
    assert "bad [REDACTED] request" in message


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
