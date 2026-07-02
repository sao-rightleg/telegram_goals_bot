from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import CAPTAIN_MENU_LABELS, PARTICIPANT_MENU_LABELS
from app.bot.messages import CONSENT_ACCEPT_BUTTON, CONSENT_TEXT, UNKNOWN_USER_TEXT
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.sqlite import initialize_schema


NOW = "2026-07-02T10:00:00+05:00"


def test_start_unknown_user_sends_approved_message_and_error_notification(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, notification_bot, _repository = _build_service(tmp_path)
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404", username="missing")

    response = service.handle_start(user, occurred_at=NOW)

    assert response.text == UNKNOWN_USER_TEXT
    assert response.menu_items == ()
    assert gateway.find_participant_by_telegram_id(404) is None
    assert [message.text for message in main_bot.sent_messages] == [UNKNOWN_USER_TEXT]
    assert len(error_bot.sent_messages) == 1
    assert "unknown_telegram_user" in error_bot.sent_messages[0].text
    assert "telegram_id=404" in error_bot.sent_messages[0].text
    assert "username=missing" in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_start_known_user_without_consent_shows_consent_only(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        participants=[
            {
                "participant_id": "P001",
                "telegram_id": 1001,
                "role": "participant",
                "consent_given": False,
            }
        ],
    )
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    response = service.handle_start(user, occurred_at=NOW)

    assert response.text == CONSENT_TEXT
    assert response.buttons == (CONSENT_ACCEPT_BUTTON,)
    assert response.menu_items == ()
    assert [message.text for message in main_bot.sent_messages] == [CONSENT_TEXT]
    assert error_bot.sent_messages == []
    assert repository.get(1001).flow == "consent"


def test_accept_consent_updates_sheets_and_shows_menu(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        participants=[
            {
                "participant_id": "P001",
                "telegram_id": 1001,
                "role": "participant",
                "consent_given": False,
            }
        ],
    )
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    response = service.accept_consent(user, consent_given_at=NOW)

    participant = gateway.find_participant_by_telegram_id(1001)
    assert participant["consent_given"] is True
    assert participant["consent_given_at"] == NOW
    assert [item.label for item in response.menu_items] == PARTICIPANT_MENU_LABELS
    assert PARTICIPANT_MENU_LABELS == main_bot.sent_messages[-1].text.splitlines()
    assert error_bot.sent_messages == []
    assert repository.get(1001).flow == "idle"


def test_start_known_user_with_consent_shows_role_menu(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        participants=[
            {
                "participant_id": "P001",
                "telegram_id": 1001,
                "role": "captain",
                "consent_given": True,
            }
        ],
    )
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    response = service.handle_start(user, occurred_at=NOW)

    assert [item.label for item in response.menu_items] == CAPTAIN_MENU_LABELS
    assert CAPTAIN_MENU_LABELS == main_bot.sent_messages[-1].text.splitlines()
    assert error_bot.sent_messages == []
    assert repository.get(1001).flow == "idle"


def test_consent_accept_unknown_user_does_not_write_consent(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, notification_bot, repository = _build_service(tmp_path)
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")

    response = service.accept_consent(user, consent_given_at=NOW)

    assert response.text == UNKNOWN_USER_TEXT
    assert [message.text for message in main_bot.sent_messages] == [UNKNOWN_USER_TEXT]
    assert len(error_bot.sent_messages) == 1
    assert notification_bot.sent_messages == []
    assert repository.get(404) is None


def test_unknown_user_error_uses_error_bot_only(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, notification_bot, _repository = _build_service(tmp_path)

    service.handle_start(TelegramUserContext(telegram_id=404, chat_id="chat-404"), occurred_at=NOW)

    assert len(main_bot.sent_messages) == 1
    assert len(error_bot.sent_messages) == 1
    assert notification_bot.sent_messages == []


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
) -> tuple[
    ParticipantFlowService,
    FakeSheetsGateway,
    FakeBotClient,
    FakeBotClient,
    FakeBotClient,
    DialogStateRepository,
]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(participants=participants or [])
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    repository = DialogStateRepository(db_path)
    return (
        ParticipantFlowService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            dialog_states=repository,
        ),
        gateway,
        main_bot,
        error_bot,
        notification_bot,
        repository,
    )
