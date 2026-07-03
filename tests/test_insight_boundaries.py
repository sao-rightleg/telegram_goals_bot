import ast
import sqlite3
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.messages import INSIGHT_MISSING_TEXT, INSIGHT_SUCCESS_TEXT, INSIGHT_VOICE_NOT_AVAILABLE_TEXT
from app.services.insights import InsightService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.services.voice_messages import VoiceMessageInput, VoiceMessageResult
from app.sheets.gateway import FakeSheetsGateway
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
LATER = datetime(2026, 7, 2, 10, 5, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
CAPTAIN = TelegramUserContext(telegram_id=2001, chat_id="chat-2001")
PARTICIPANT = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")


def test_captain_sees_only_personal_insights(tmp_path: Path) -> None:
    service, _gateway, _main_bot, error_bot, _db_path = _build_service(
        tmp_path,
        participants=[
            _participant("P100", 2001, role="captain"),
            _participant("P101", 1001, role="participant"),
        ],
        insights=[
            _insight("I-CAPTAIN", "P100", "Личный инсайт капитана"),
            _insight("I-TEAM", "P101", "Инсайт участника команды"),
        ],
    )

    list_response = service.list_insights(CAPTAIN, page_index=0, now=NOW)
    own_response = service.get_full_text(CAPTAIN, insight_id="I-CAPTAIN", now=NOW)
    team_response = service.get_full_text(CAPTAIN, insight_id="I-TEAM", now=NOW)

    assert "Личный инсайт капитана" in list_response.text
    assert "Инсайт участника команды" not in list_response.text
    assert "Личный инсайт капитана" in own_response.text
    assert team_response.text == INSIGHT_MISSING_TEXT
    assert "Инсайт участника команды" not in error_bot.sent_messages[-1].text


def test_insight_save_does_not_change_weekly_progress(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
        planned_steps=[
            _step("S001", "P001", "G001", "open"),
            _step("S002", "P001", "G001", "closed"),
        ],
        weekly_reports=[
            {
                "weekly_report_id": "WR001",
                "participant_id": "P001",
                "week_number": 3,
                "status_code": "green",
                "score": 1,
            }
        ],
        weekly_report_steps=[
            {
                "weekly_report_step_id": "WRS001",
                "weekly_report_id": "WR001",
                "step_id": "S002",
                "relation_status": "closed",
            }
        ],
    )
    before_steps = gateway.list_planned_steps("P001", "G001")
    before_reports = gateway.list_weekly_reports()
    before_report_steps = gateway.list_weekly_report_steps()

    service.start_add(PARTICIPANT, now=NOW)
    service.add_text_message(PARTICIPANT, "Инсайт без влияния на прогресс", now=NOW)
    response = service.set_title_and_save(PARTICIPANT, "Планирование", now=LATER)

    assert response.text == INSIGHT_SUCCESS_TEXT
    assert gateway.list_planned_steps("P001", "G001") == before_steps
    assert gateway.list_weekly_reports() == before_reports
    assert gateway.list_weekly_report_steps() == before_report_steps
    assert len(gateway.list_insights()) == 1
    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_voice_insight_does_not_change_weekly_status_or_progress(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
        planned_steps=[
            _step("S001", "P001", "G001", "open"),
            _step("S002", "P001", "G001", "closed"),
        ],
        weekly_reports=[
            {
                "weekly_report_id": "WR001",
                "participant_id": "P001",
                "week_number": 3,
                "status_code": "green",
                "score": 1,
            }
        ],
        weekly_report_steps=[
            {
                "weekly_report_step_id": "WRS001",
                "weekly_report_id": "WR001",
                "step_id": "S002",
                "relation_status": "closed",
            }
        ],
    )
    drafts = InsightDraftRepository(db_path)
    service = replace(service, drafts=drafts, voice_messages=AcceptingVoiceService(drafts=drafts))
    before_steps = gateway.list_planned_steps("P001", "G001")
    before_reports = gateway.list_weekly_reports()
    before_report_steps = gateway.list_weekly_report_steps()

    service.start_add(PARTICIPANT, now=NOW)
    voice_response = service.add_voice_message(
        PARTICIPANT,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        now=NOW,
        telegram_message_id=501,
    )
    save_response = service.set_title_and_save(PARTICIPANT, "Планирование", now=LATER)

    assert voice_response.text == "Голосовое принято и расшифровано."
    assert save_response.text == INSIGHT_SUCCESS_TEXT
    assert gateway.list_planned_steps("P001", "G001") == before_steps
    assert gateway.list_weekly_reports() == before_reports
    assert gateway.list_weekly_report_steps() == before_report_steps
    assert len(gateway.list_insights()) == 1


def test_voice_message_creates_no_audio_or_transcription_state(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(PARTICIPANT, now=NOW)
    response = service.reject_voice_message(PARTICIPANT, now=NOW)

    assert response.text == INSIGHT_VOICE_NOT_AVAILABLE_TEXT
    assert gateway.list_insights() == []
    with sqlite3.connect(db_path) as connection:
        attachment_count = connection.execute("SELECT COUNT(*) FROM draft_attachments").fetchone()[0]
        voice_message_count = connection.execute(
            "SELECT COUNT(*) FROM draft_messages WHERE message_type = 'voice_transcription'"
        ).fetchone()[0]

    assert attachment_count == 0
    assert voice_message_count == 0


def test_out_of_scope_dependencies_are_not_imported(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )
    service.start_add(PARTICIPANT, now=NOW)

    forbidden_import_roots = {
        "aiogram",
        "telegram",
        "google",
        "gspread",
        "reportlab",
        "weasyprint",
        "openai",
        "whisper",
        "docker",
        "celery",
        "redis",
    }
    checked_paths = [
        Path("app/services/insights.py"),
        Path("app/storage/insight_drafts.py"),
        Path("app/sheets/gateway.py"),
        Path("app/bot/messages.py"),
    ]

    for path in checked_paths:
        assert _import_roots(path).isdisjoint(forbidden_import_roots), path

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_error_notifications_do_not_include_full_insight_text(tmp_path: Path) -> None:
    private_text = "Очень личный полный текст инсайта, который нельзя отправлять админам."
    service, _gateway, _main_bot, error_bot, _db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        insights=[_insight("I-PRIVATE", "P002", private_text)],
    )

    response = service.get_full_text(PARTICIPANT, insight_id="I-PRIVATE", now=NOW)

    assert response.text == INSIGHT_MISSING_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "missing_insight_callback" in error_bot.sent_messages[0].text
    assert private_text not in error_bot.sent_messages[0].text
    assert "token" not in error_bot.sent_messages[0].text.lower()


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_reports: list[dict[str, object]] | None = None,
    weekly_report_steps: list[dict[str, object]] | None = None,
    insights: list[dict[str, object]] | None = None,
) -> tuple[InsightService, FakeSheetsGateway, FakeBotClient, FakeBotClient, Path]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(
        participants=participants,
        goals=goals or [],
        planned_steps=planned_steps or [],
        weekly_reports=weekly_reports or [],
        weekly_report_steps=weekly_report_steps or [],
        insights=insights or [],
    )
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return (
        InsightService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            drafts=InsightDraftRepository(db_path),
        ),
        gateway,
        main_bot,
        error_bot,
        db_path,
    )


def _participant(participant_id: str, telegram_id: int, *, role: str = "participant") -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": "T001",
        "consent_given": True,
    }


def _goal(goal_id: str, participant_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": "Цель",
        "goal_status": "active",
    }


def _step(step_id: str, participant_id: str, goal_id: str, status: str) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": 1,
        "step_title": f"Шаг {step_id}",
        "step_description": "",
        "step_status": status,
    }


def _insight(insight_id: str, participant_id: str, text: str) -> dict[str, object]:
    return {
        "insight_id": insight_id,
        "participant_id": participant_id,
        "goal_id": "G001",
        "week_number": 4,
        "insight_scope": "current_week",
        "insight_title": f"Заголовок {insight_id}",
        "insight_date": "2026-07-02",
        "insight_text": text,
        "created_by_id": participant_id,
        "created_by_role": "captain" if participant_id == "P100" else "participant",
        "created_at": "2026-07-02T10:00:00+05:00",
    }


def _import_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
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
    return imports


class AcceptingVoiceService:
    def __init__(self, drafts: InsightDraftRepository) -> None:
        self._drafts = drafts

    def handle_voice(self, request: VoiceMessageInput) -> VoiceMessageResult:
        self._drafts.append_voice_transcription(
            request.user.telegram_id,
            telegram_file_id=request.telegram_file_id,
            local_file_path=Path("data/audio/2026/week_04/personal_insights/P001/voice_1001_501.ogg"),
            duration_seconds=request.duration_seconds,
            transcription_text="Голосовой инсайт",
            occurred_at=request.now.isoformat(),
            telegram_message_id=request.telegram_message_id,
        )
        return VoiceMessageResult(text="Голосовое принято и расшифровано.", accepted=True)
