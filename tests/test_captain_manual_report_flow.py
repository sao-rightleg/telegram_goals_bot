from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.messages import (
    CAPTAIN_EMPTY_REPORT_TEXT,
    CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT,
    CAPTAIN_MANUAL_REPORT_LATE_TEXT,
    CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT,
    WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT,
    WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT,
)
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.captains import CaptainService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.services.weekly_report_models import WeeklyReportStatus
from app.sheets.gateway import FakeSheetsGateway
from app.storage.sqlite import initialize_schema
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))
LATE = datetime(2026, 7, 5, 23, 59, 1, tzinfo=ZoneInfo(TIMEZONE_NAME))


def test_captain_green_manual_report_saves_report_steps_and_submitter(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    _prepare_green(service, captain)
    service.add_text_message(captain, "Участник закрыл первый шаг", now=NOW)

    response = service.finalize_manual_report(captain, now=NOW)

    assert response.text == CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT
    assert drafts.get_active_draft(captain.telegram_id) is None
    assert gateway.list_weekly_reports() == [
        {
            "weekly_report_id": "WR:P001:week-04",
            "participant_id": "P001",
            "team_id": "T001",
            "goal_id": "G001",
            "week_number": 4,
            "status_code": "green",
            "status_symbol": "🟩",
            "score": 1,
            "report_text": "Участник закрыл первый шаг",
            "transcription_text": "",
            "audio_file_path": "",
            "audio_deleted_at": "",
            "submitted_at": NOW.isoformat(),
            "submitted_by_id": "C001",
            "submitted_by_role": "captain",
            "flow_source": "captain_manual",
        }
    ]
    assert gateway.list_weekly_report_steps() == [
        {
            "weekly_report_step_id": "WRS:WR:P001:week-04:S001",
            "weekly_report_id": "WR:P001:week-04",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_id": "S001",
            "week_number": 4,
            "relation_status": "closed",
            "created_at": NOW.isoformat(),
        }
    ]
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "closed"


def test_captain_blue_manual_report_writes_partial_relations_without_closing_steps(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.BLUE, now=NOW)
    service.select_steps(captain, ["S001", "S002"], now=NOW)
    service.add_text_message(captain, "Есть частичный прогресс", now=NOW)

    response = service.finalize_manual_report(captain, now=NOW)

    assert response.text == CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT
    assert drafts.get_active_draft(captain.telegram_id) is None
    row = gateway.list_weekly_reports()[0]
    assert row["participant_id"] == "P001"
    assert row["submitted_by_id"] == "C001"
    assert row["submitted_by_role"] == "captain"
    assert row["flow_source"] == "captain_manual"
    assert row["status_code"] == "blue"
    assert row["status_symbol"] == "🟦"
    assert row["score"] == 0.5
    assert [row["relation_status"] for row in gateway.list_weekly_report_steps()] == ["partial", "partial"]
    assert [row["step_status"] for row in gateway.list_planned_steps("P001", "G001")] == [
        "open",
        "open",
        "closed",
    ]


def test_captain_red_manual_report_does_not_require_steps(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.RED, now=NOW)
    service.add_text_message(captain, "Участник не сделал победу недели", now=NOW)

    response = service.finalize_manual_report(captain, now=NOW)

    assert response.text == CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT
    assert drafts.get_active_draft(captain.telegram_id) is None
    assert gateway.list_weekly_reports()[0]["status_code"] == "red"
    assert gateway.list_weekly_reports()[0]["status_symbol"] == "🟥"
    assert gateway.list_weekly_reports()[0]["score"] == 0
    assert gateway.list_weekly_report_steps() == []


def test_captain_manual_report_requires_text_before_finalize(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    _prepare_green(service, captain)

    response = service.finalize_manual_report(captain, now=NOW)

    assert response.text == CAPTAIN_EMPTY_REPORT_TEXT
    assert gateway.list_weekly_reports() == []
    assert drafts.get_active_draft(captain.telegram_id) is not None


def test_captain_manual_report_rejects_duplicate_before_final_save(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    _prepare_green(service, captain)
    service.add_text_message(captain, "Участник закрыл первый шаг", now=NOW)
    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4})

    response = service.finalize_manual_report(captain, now=NOW)

    assert response.text == CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT
    assert gateway.list_weekly_reports() == [
        {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}
    ]
    assert gateway.list_weekly_report_steps() == []
    assert drafts.get_active_draft(captain.telegram_id) is not None


def test_captain_manual_report_rejects_late_before_final_save(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    _prepare_green(service, captain)
    service.add_text_message(captain, "Участник закрыл первый шаг", now=NOW)

    response = service.finalize_manual_report(captain, now=LATE)

    assert response.text == CAPTAIN_MANUAL_REPORT_LATE_TEXT
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "open"
    assert drafts.get_active_draft(captain.telegram_id) is not None


def test_captain_manual_report_revalidates_invalid_steps_before_final_save(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.GREEN, now=NOW)

    response = service.select_steps(captain, ["S003"], now=NOW)

    assert response.text == WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT
    assert gateway.list_weekly_reports() == []
    assert drafts.get_active_draft(captain.telegram_id).selected_step_ids == ()


def test_captain_blue_manual_report_requires_valid_steps(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.BLUE, now=NOW)

    response = service.select_steps(captain, ["S999"], now=NOW)

    assert response.text == WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT
    assert drafts.get_active_draft(captain.telegram_id).selected_step_ids == ()


def _prepare_green(service: CaptainService, captain: TelegramUserContext) -> None:
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.GREEN, now=NOW)
    service.select_steps(captain, ["S001"], now=NOW)


def _service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_reports: list[dict[str, object]] | None = None,
) -> tuple[CaptainService, FakeSheetsGateway, WeeklyReportDraftRepository, FakeBotClient, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    drafts = WeeklyReportDraftRepository(db_path)
    gateway = FakeSheetsGateway(
        participants=participants if participants is not None else [_captain(), _participant()],
        goals=goals if goals is not None else [_goal()],
        planned_steps=planned_steps if planned_steps is not None else _planned_steps(),
        weekly_reports=weekly_reports or [],
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
        CaptainService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            drafts=drafts,
        ),
        gateway,
        drafts,
        main_bot,
        error_bot,
    )


def _captain_user() -> TelegramUserContext:
    return TelegramUserContext(telegram_id=2001, chat_id="chat-2001", username="captain")


def _captain() -> dict[str, object]:
    return {
        "participant_id": "C001",
        "telegram_id": 2001,
        "role": "captain",
        "team_id": "T001",
        "consent_given": True,
        "full_name": "Капитан",
        "status": "active",
    }


def _participant() -> dict[str, object]:
    return {
        "participant_id": "P001",
        "telegram_id": 1001,
        "role": "participant",
        "team_id": "T001",
        "consent_given": True,
        "full_name": "Участник",
        "status": "active",
    }


def _goal() -> dict[str, object]:
    return {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}


def _planned_steps() -> list[dict[str, object]]:
    return [
        _step("S001", 1, "Первый шаг", "open"),
        _step("S002", 2, "Второй шаг", "open"),
        _step("S003", 3, "Закрытый шаг", "closed"),
    ]


def _step(step_id: str, number: int, title: str, status: str) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": "P001",
        "goal_id": "G001",
        "step_number": number,
        "step_title": title,
        "step_status": status,
    }
