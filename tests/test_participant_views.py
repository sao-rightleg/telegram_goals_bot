from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import MenuAction
from app.bot.messages import CONSENT_TEXT, MISSING_DATA_TEXT, NOT_AVAILABLE_TEXT
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.sqlite import initialize_schema


NOW = "2026-07-02T10:00:00+05:00"


def test_goal_view_shows_current_participant_goal_only(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        goals=[
            _goal("G001", "P001", "Моя цель"),
            _goal("G002", "P002", "Чужая цель"),
        ],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_GOAL,
        occurred_at=NOW,
    )

    assert "Моя цель" in response.text
    assert "Чужая цель" not in response.text
    assert main_bot.sent_messages[-1].text == response.text
    assert error_bot.sent_messages == []


def test_steps_view_shows_current_participant_steps_only(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001), _participant("P002", 1002)],
        goals=[_goal("G001", "P001", "Моя цель"), _goal("G002", "P002", "Чужая цель")],
        planned_steps=[
            _step("S001", "P001", "G001", 1, "Мой открытый шаг", "open"),
            _step("S002", "P001", "G001", 2, "Мой закрытый шаг", "closed"),
            _step("S003", "P002", "G002", 1, "Чужой шаг", "closed"),
        ],
    )

    before = gateway.list_planned_steps("P001", "G001")
    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_STEPS,
        occurred_at=NOW,
    )

    assert "Мой открытый шаг" in response.text
    assert "Мой закрытый шаг" in response.text
    assert "Чужой шаг" not in response.text
    assert gateway.list_planned_steps("P001", "G001") == before


def test_progress_view_uses_planned_steps_as_primary_progress(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001", "Моя цель")],
        planned_steps=[
            _step("S001", "P001", "G001", 1, "Шаг 1", "closed"),
            _step("S002", "P001", "G001", 2, "Шаг 2", "closed"),
            _step("S003", "P001", "G001", 3, "Шаг 3", "closed"),
            _step("S004", "P001", "G001", 4, "Шаг 4", "open"),
            _step("S005", "P001", "G001", 5, "Шаг 5", "open"),
            _step("S006", "P001", "G001", 6, "Шаг 6", "open"),
        ],
        weekly_reports=[
            {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 1, "status_symbol": "🟥", "status_code": "red"}
        ],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_PROGRESS,
        occurred_at=NOW,
    )

    assert "50%" in response.text
    assert "■■■□□□" in response.text


def test_weekly_history_is_secondary_when_available(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001", "Моя цель")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Шаг 1", "closed")],
        weekly_reports=[
            {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 1, "status_symbol": "🟩", "status_code": "green"}
        ],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_PROGRESS,
        occurred_at=NOW,
    )

    assert "История недель:" in response.text
    assert "Неделя 1: 🟩" in response.text


def test_view_requires_consent_before_data(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001, consent_given=False)],
        goals=[_goal("G001", "P001", "Скрытая цель")],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_GOAL,
        occurred_at=NOW,
    )

    assert response.text == CONSENT_TEXT
    assert "Скрытая цель" not in main_bot.sent_messages[-1].text
    assert error_bot.sent_messages == []


def test_missing_goal_sends_safe_message_and_admin_error(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[],
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
    assert "active_goal" in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_out_of_scope_actions_are_inert(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, _notification_bot = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001, role="captain")],
        weekly_reports=[{"weekly_report_id": "WR001", "participant_id": "P001"}],
    )

    for action in (
        MenuAction.VIEW_INSIGHTS,
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
    assert gateway.list_weekly_reports() == [{"weekly_report_id": "WR001", "participant_id": "P001"}]
    assert gateway.list_insights() == []


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_reports: list[dict[str, object]] | None = None,
) -> tuple[ParticipantFlowService, FakeSheetsGateway, FakeBotClient, FakeBotClient, FakeBotClient]:
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
    return service, gateway, main_bot, error_bot, notification_bot


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    role: str = "participant",
    consent_given: bool = True,
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": "T001",
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
