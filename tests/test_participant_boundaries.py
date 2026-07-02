import ast
from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import MenuAction
from app.bot.messages import CONSENT_TEXT, MISSING_DATA_TEXT, NOT_AVAILABLE_TEXT
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, initialize_schema, list_tables


NOW = "2026-07-02T10:00:00+05:00"


def test_participant_cannot_view_another_participants_goal_or_steps(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot, _db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        goals=[_goal("G001", "P001", "Цель P001"), _goal("G002", "P002", "Цель P002")],
        planned_steps=[
            _step("S001", "P001", "G001", 1, "Шаг P001", "open"),
            _step("S002", "P002", "G002", 1, "Шаг P002", "open"),
        ],
    )

    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")
    goal_response = service.handle_menu_action(user, MenuAction.VIEW_GOAL, occurred_at=NOW)
    steps_response = service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)

    assert "Цель P001" in goal_response.text
    assert "Цель P002" not in goal_response.text
    assert "Шаг P001" in steps_response.text
    assert "Шаг P002" not in steps_response.text


def test_no_business_data_before_consent_across_actions(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot, _db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001, consent_given=False)],
        goals=[_goal("G001", "P001", "Скрытая цель")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Скрытый шаг", "closed")],
    )

    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")
    for action in (MenuAction.VIEW_GOAL, MenuAction.VIEW_STEPS, MenuAction.VIEW_PROGRESS):
        response = service.handle_menu_action(user, action, occurred_at=NOW)
        assert response.text == CONSENT_TEXT

    sent_text = "\n".join(message.text for message in main_bot.sent_messages)
    assert "Скрытая цель" not in sent_text
    assert "Скрытый шаг" not in sent_text
    assert error_bot.sent_messages == []


def test_missing_required_data_routes_error_bot_only(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, notification_bot, _db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001, team_id=None)],
        goals=[_goal("G001", "P001", "Цель P001")],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_GOAL,
        occurred_at=NOW,
    )

    assert response.text == MISSING_DATA_TEXT
    assert main_bot.sent_messages[-1].text == MISSING_DATA_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "missing_required_data" in error_bot.sent_messages[0].text
    assert "type=team_id" in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_sqlite_contains_no_participant_business_tables_after_flows(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001", "Цель P001")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Шаг P001", "closed")],
    )

    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")
    service.handle_start(user, occurred_at=NOW)
    service.handle_menu_action(user, MenuAction.VIEW_GOAL, occurred_at=NOW)
    service.handle_menu_action(user, MenuAction.VIEW_PROGRESS, occurred_at=NOW)

    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


def test_feature_does_not_introduce_out_of_scope_dependencies_or_artifacts(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, notification_bot, db_path = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001, role="captain")],
        weekly_reports=[{"weekly_report_id": "WR001", "participant_id": "P001"}],
    )

    insight_response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_INSIGHTS,
        occurred_at=NOW,
    )
    assert insight_response.text == "Мои инсайты"

    for action in (
        MenuAction.VIEW_TEAM,
        MenuAction.CAPTAIN_MANUAL_REPORT,
        MenuAction.VIEW_TEAM_REPORT,
    ):
        response = service.handle_menu_action(
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
            action,
            occurred_at=NOW,
        )
        assert response.text == NOT_AVAILABLE_TEXT

    assert len(main_bot.sent_messages) == 4
    assert error_bot.sent_messages == []
    assert notification_bot.sent_messages == []
    assert gateway.list_weekly_reports() == [{"weekly_report_id": "WR001", "participant_id": "P001"}]
    assert gateway.list_insights() == []
    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)

    forbidden_import_roots = {
        "aiogram",
        "telegram",
        "google",
        "gspread",
        "reportlab",
        "weasyprint",
        "openai",
        "whisper",
        "celery",
        "redis",
        "psycopg",
        "psycopg2",
    }
    for path in (
        Path("app/services/participant_flows.py"),
        Path("app/bot/messages.py"),
        Path("app/bot/menus.py"),
        Path("app/sheets/gateway.py"),
        Path("app/storage/dialog_state.py"),
    ):
        imports = _import_roots(path)
        assert imports.isdisjoint(forbidden_import_roots), path


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_reports: list[dict[str, object]] | None = None,
) -> tuple[
    ParticipantFlowService,
    FakeSheetsGateway,
    FakeBotClient,
    FakeBotClient,
    FakeBotClient,
    Path,
]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(
        participants=participants or [],
        goals=goals or [],
        planned_steps=planned_steps or [],
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
    service = ParticipantFlowService(
        sheets=gateway,
        main_bot=main_bot,
        notification_router=router,
        dialog_states=DialogStateRepository(db_path),
    )
    return service, gateway, main_bot, error_bot, notification_bot, db_path


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    role: str = "participant",
    consent_given: bool = True,
    team_id: str | None = "T001",
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": team_id,
        "consent_given": consent_given,
    }


def _goal(goal_id: str, participant_id: str, title: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": title,
        "goal_description": f"Описание {title}",
        "goal_value_amount": "100000",
        "goal_value_currency": "RUB",
        "permission_condition": "Оплата получена",
        "goal_status": "active",
    }


def _step(
    step_id: str,
    participant_id: str,
    goal_id: str,
    number: int,
    title: str,
    status: str,
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": number,
        "step_title": title,
        "step_description": "",
        "step_status": status,
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
