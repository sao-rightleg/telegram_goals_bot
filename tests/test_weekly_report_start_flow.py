from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.messages import CONSENT_TEXT, MISSING_DATA_TEXT, UNKNOWN_USER_TEXT, WEEKLY_REPORT_LATE_TEXT
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.services.weekly_report_models import WeeklyReportStatus
from app.services.weekly_reports import WeeklyReportService
from app.sheets.gateway import FakeSheetsGateway
from app.storage.sqlite import initialize_schema
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))
LATE = datetime(2026, 7, 5, 23, 59, 1, tzinfo=ZoneInfo(TIMEZONE_NAME))


def test_start_report_identifies_participant_by_telegram_id(tmp_path: Path) -> None:
    service, gateway, drafts, main_bot, _error_bot = _service(tmp_path)
    user = _user()

    response = service.start_report(user, now=NOW)

    assert response.chat_id == "chat-1001"
    assert "На этой неделе у тебя остались незакрытые шаги:" in response.text
    assert "1. Первый шаг" in response.text
    assert "2. Второй шаг" in response.text
    assert "Закрытый шаг" not in response.text
    assert response.buttons == ("🟩 Победа есть", "🟦 Частично", "🟥 Победы нет")
    assert main_bot.sent_messages[-1].text == response.text

    draft = drafts.get_active_draft(1001)
    assert draft is not None
    assert draft.participant_id == "P001"
    assert draft.week_number == 4
    assert gateway.list_weekly_reports() == []


def test_start_report_for_step_preselects_open_step(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()

    response = service.start_report_for_step(user, step_id="S001", now=NOW)

    draft = drafts.get_active_draft(1001)
    assert "Выбери статус недели." in response.text
    assert draft is not None
    assert draft.selected_step_ids == ("S001",)

    status_response = service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)

    assert status_response.text == "Что именно ты сделал?"
    assert drafts.get_active_draft(1001).selected_step_ids == ("S001",)


def test_start_report_for_step_rejects_closed_step(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)

    response = service.start_report_for_step(_user(), step_id="S003", now=NOW)

    assert response.text == "Выбери один или несколько открытых шагов."
    assert drafts.get_active_draft(1001) is None


def test_unknown_user_cannot_start_weekly_report(tmp_path: Path) -> None:
    service, _gateway, drafts, main_bot, error_bot = _service(tmp_path, participants=[])

    response = service.start_report(_user(), now=NOW)

    assert response.text == UNKNOWN_USER_TEXT
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == UNKNOWN_USER_TEXT
    assert "unknown_telegram_user" in error_bot.sent_messages[-1].text


def test_non_consenting_user_cannot_start_weekly_report(tmp_path: Path) -> None:
    service, _gateway, drafts, main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant(consent_given=False)],
    )

    response = service.start_report(_user(), now=NOW)

    assert response.text == CONSENT_TEXT
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == CONSENT_TEXT


def test_start_report_rejects_late_week(tmp_path: Path) -> None:
    service, _gateway, drafts, main_bot, _error_bot = _service(tmp_path)

    response = service.start_report(_user(), now=LATE)

    assert response.text == WEEKLY_REPORT_LATE_TEXT
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == WEEKLY_REPORT_LATE_TEXT


def test_start_report_rejects_duplicate_weekly_report(tmp_path: Path) -> None:
    service, _gateway, drafts, main_bot, _error_bot = _service(
        tmp_path,
        weekly_reports=[{"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}],
    )

    response = service.start_report(_user(), now=NOW)

    assert response.text == "Отчёт за эту неделю уже принят."
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == "Отчёт за эту неделю уже принят."


def test_start_report_handles_missing_goal_or_steps(tmp_path: Path) -> None:
    service, _gateway, drafts, main_bot, error_bot = _service(tmp_path, goals=[])

    response = service.start_report(_user(), now=NOW)

    assert response.text == MISSING_DATA_TEXT
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == MISSING_DATA_TEXT
    assert "missing_required_data" in error_bot.sent_messages[-1].text
    assert "active_goal" in error_bot.sent_messages[-1].text


def _service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_reports: list[dict[str, object]] | None = None,
) -> tuple[WeeklyReportService, FakeSheetsGateway, WeeklyReportDraftRepository, FakeBotClient, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    drafts = WeeklyReportDraftRepository(db_path)
    gateway = FakeSheetsGateway(
        participants=participants if participants is not None else [_participant()],
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
        WeeklyReportService(
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


def _user() -> TelegramUserContext:
    return TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001")


def _participant(*, consent_given: bool = True) -> dict[str, object]:
    return {
        "participant_id": "P001",
        "telegram_id": 1001,
        "role": "participant",
        "team_id": "T001",
        "consent_given": consent_given,
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
