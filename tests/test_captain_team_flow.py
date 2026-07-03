from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.messages import (
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_TEAM_TITLE_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
)
from app.services.captains import CaptainService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway


NOW = "2026-07-02T10:00:00+05:00"


def test_captain_can_view_only_own_team() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", team_id="T001", full_name="Капитан команды"),
            _participant("P001", 1001, team_id="T001", full_name="Анна Своя"),
            _participant("P002", 1002, team_id="T001", full_name="Борис Свой"),
            _participant("P003", 1003, team_id="T002", full_name="Олег Чужой"),
        ],
    )

    response = service.show_team(
        TelegramUserContext(telegram_id=2001, chat_id="chat-2001"),
        occurred_at=NOW,
    )

    assert response.text.startswith(CAPTAIN_TEAM_TITLE_TEXT)
    assert "Капитан команды" in response.text
    assert "Анна Своя" in response.text
    assert "Борис Свой" in response.text
    assert "Олег Чужой" not in response.text
    assert "P001" not in response.text
    assert "T001" not in response.text
    assert main_bot.sent_messages[-1].text == response.text
    assert error_bot.sent_messages == []


def test_non_captain_cannot_view_team() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("P001", 1001, role="participant", team_id="T001", full_name="Анна Участник"),
            _participant("P002", 1002, role="participant", team_id="T001", full_name="Борис Участник"),
        ],
    )

    response = service.show_team(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        occurred_at=NOW,
    )

    assert response.text == CAPTAIN_ONLY_TEXT
    assert "Анна Участник" not in response.text
    assert "Борис Участник" not in response.text
    assert main_bot.sent_messages[-1].text == CAPTAIN_ONLY_TEXT
    assert error_bot.sent_messages == []


def test_captain_without_team_routes_missing_data_to_admin() -> None:
    service, _gateway, main_bot, error_bot, notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", team_id=None, full_name="Капитан без команды"),
        ],
    )

    response = service.show_team(
        TelegramUserContext(telegram_id=2001, chat_id="chat-2001"),
        occurred_at=NOW,
    )

    assert response.text == MISSING_DATA_TEXT
    assert main_bot.sent_messages[-1].text == MISSING_DATA_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "missing_required_data" in error_bot.sent_messages[0].text
    assert "type=team_id" in error_bot.sent_messages[0].text
    assert "telegram_id=2001" in error_bot.sent_messages[0].text
    assert "participant_id=C001" in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_unknown_user_keeps_existing_unknown_user_behavior() -> None:
    service, _gateway, main_bot, error_bot, notification_bot = _build_service(participants=[])

    response = service.show_team(
        TelegramUserContext(telegram_id=9999, chat_id="chat-9999", username="unknown_user"),
        occurred_at=NOW,
    )

    assert response.text == UNKNOWN_USER_TEXT
    assert main_bot.sent_messages[-1].text == UNKNOWN_USER_TEXT
    assert len(error_bot.sent_messages) == 1
    assert "unknown_telegram_user" in error_bot.sent_messages[0].text
    assert "telegram_id=9999" in error_bot.sent_messages[0].text
    assert "username=unknown_user" in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_captain_without_consent_gets_consent_prompt_without_team_data() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", consent_given=False, full_name="Капитан"),
            _participant("P001", 1001, team_id="T001", full_name="Анна Своя"),
        ],
    )

    response = service.show_team(
        TelegramUserContext(telegram_id=2001, chat_id="chat-2001"),
        occurred_at=NOW,
    )

    assert response.text == CONSENT_TEXT
    assert response.buttons == (CONSENT_ACCEPT_BUTTON,)
    assert "Анна Своя" not in response.text
    assert main_bot.sent_messages[-1].text == CONSENT_TEXT
    assert error_bot.sent_messages == []


def _build_service(
    *,
    participants: list[dict[str, object]],
) -> tuple[CaptainService, FakeSheetsGateway, FakeBotClient, FakeBotClient, FakeBotClient]:
    gateway = FakeSheetsGateway(participants=participants)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    service = CaptainService(
        sheets=gateway,
        main_bot=main_bot,
        notification_router=router,
    )
    return service, gateway, main_bot, error_bot, notification_bot


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    role: str = "participant",
    team_id: str | None = "T001",
    consent_given: bool = True,
    full_name: str = "Участник",
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": team_id,
        "consent_given": consent_given,
        "full_name": full_name,
    }
