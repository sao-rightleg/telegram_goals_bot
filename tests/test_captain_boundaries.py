import ast
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.messages import (
    CAPTAIN_DROPPED_PARTICIPANT_TEXT,
    CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT,
    CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT,
    CAPTAIN_MANUAL_REPORT_LATE_TEXT,
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


def test_forged_other_team_participant_id_is_rejected(tmp_path: Path) -> None:
    service, gateway, drafts, main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("C001", 2001, role="captain", team_id="T001", full_name="Капитан"),
            _participant("P001", 1001, team_id="T001", full_name="Свой участник"),
            _participant("P999", 1999, team_id="T999", full_name="Чужой участник"),
        ],
        goals=[_goal("G999", "P999")],
        planned_steps=[_step("S999", "P999", "G999", "Чужой шаг")],
    )

    response = service.start_manual_report(_captain_user(), "P999", now=NOW)

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT
    assert "Чужой участник" not in response.text
    assert "P999" not in response.text
    assert "T999" not in response.text
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert drafts.get_active_draft(2001) is None
    assert main_bot.sent_messages[-1].text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT


def test_dropped_participant_manual_report_is_rejected(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("C001", 2001, role="captain", team_id="T001"),
            _participant("P001", 1001, team_id="T001", status="Dropped "),
        ],
    )

    response = service.start_manual_report(_captain_user(), "P001", now=NOW)

    assert response.text == CAPTAIN_DROPPED_PARTICIPANT_TEXT
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert drafts.get_active_draft(2001) is None


def test_duplicate_report_attempt_creates_no_new_report_or_step_relation(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(
        tmp_path,
        weekly_reports=[{"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}],
    )

    response = service.start_manual_report(_captain_user(), "P001", now=NOW)

    assert response.text == CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT
    assert gateway.list_weekly_reports() == [
        {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}
    ]
    assert gateway.list_weekly_report_steps() == []
    assert drafts.get_active_draft(2001) is None


def test_captain_manual_report_after_deadline_is_rejected(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    _prepare_green(service, captain)
    service.add_text_message(captain, "Участник сделал шаг", now=NOW)

    response = service.finalize_manual_report(captain, now=LATE)

    assert response.text == CAPTAIN_MANUAL_REPORT_LATE_TEXT
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "open"
    assert drafts.get_active_draft(2001) is not None


def test_invalid_or_closed_step_selection_is_rejected(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    captain = _captain_user()
    service.start_manual_report(captain, "P001", now=NOW)
    service.select_status(captain, WeeklyReportStatus.GREEN, now=NOW)

    closed_response = service.select_steps(captain, ["S003"], now=NOW)
    invalid_response = service.select_steps(captain, ["S999"], now=NOW)

    assert closed_response.text == WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT
    assert invalid_response.text == WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT
    assert drafts.get_active_draft(2001).selected_step_ids == ()
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert gateway.list_planned_steps("P001", "G001")[2]["step_status"] == "closed"


def test_captain_flow_does_not_import_out_of_scope_runtime_dependencies() -> None:
    forbidden_roots = {
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
    for module_path in (
        Path("app/services/captains.py"),
        Path("app/storage/weekly_report_drafts.py"),
    ):
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
        participants=participants if participants is not None else [_captain(), _target()],
        goals=goals if goals is not None else [_goal("G001", "P001")],
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
    return _participant("C001", 2001, role="captain", team_id="T001", full_name="Капитан")


def _target() -> dict[str, object]:
    return _participant("P001", 1001, team_id="T001", full_name="Участник")


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    role: str = "participant",
    team_id: str = "T001",
    full_name: str = "Участник",
    status: str = "active",
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": team_id,
        "consent_given": True,
        "full_name": full_name,
        "status": status,
    }


def _goal(goal_id: str, participant_id: str) -> dict[str, object]:
    return {"goal_id": goal_id, "participant_id": participant_id, "goal_status": "active"}


def _planned_steps() -> list[dict[str, object]]:
    return [
        _step("S001", "P001", "G001", "Первый шаг", status="open"),
        _step("S002", "P001", "G001", "Второй шаг", status="open"),
        _step("S003", "P001", "G001", "Закрытый шаг", status="closed"),
    ]


def _step(
    step_id: str,
    participant_id: str,
    goal_id: str,
    title: str,
    *,
    status: str = "open",
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": int(step_id.removeprefix("S")),
        "step_title": title,
        "step_status": status,
    }
