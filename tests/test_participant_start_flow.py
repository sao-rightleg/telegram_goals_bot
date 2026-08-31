from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import CAPTAIN_MENU_LABELS, PARTICIPANT_MENU_LABELS
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_ACCEPTED_INTRO_TEXT,
    CONSENT_DECLINE_BUTTON,
    CONSENT_DECLINE_CONFIRM_BUTTON,
    CONSENT_DECLINE_CONFIRM_TEXT,
    CONSENT_DECLINE_RECONSIDER_BUTTON,
    CONSENT_DECLINED_TEXT,
    CONSENT_TEXT,
    UNKNOWN_USER_TEXT,
)
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.registration import RegistrationDraftRepository
from app.storage.sqlite import initialize_schema


REGISTRATION_OPEN = "2026-09-09T18:00:00+05:00"
REGISTRATION_NOW = "2026-09-10T10:00:00+05:00"
REGISTRATION_CLOSED = "2026-09-16T18:00:01+05:00"


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
    assert "username=" not in error_bot.sent_messages[0].text
    assert notification_bot.sent_messages == []


def test_start_known_user_without_consent_shows_consent_and_marks_start(tmp_path: Path) -> None:
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

    response = service.handle_start(user, occurred_at=NOW)

    assert response.text == CONSENT_TEXT
    assert response.buttons == (CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON)
    assert response.menu_items == ()
    assert [message.text for message in main_bot.sent_messages] == [CONSENT_TEXT]
    participant = gateway.find_participant_by_telegram_id(1001)
    assert participant["bot_started_at"] == NOW
    assert participant["participant_stage"] == "onboarding"
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
    assert participant["participant_stage"] == "goal_setup"
    assert response.text.startswith(CONSENT_ACCEPTED_INTRO_TEXT)
    assert response.menu_items == ()
    assert PARTICIPANT_MENU_LABELS == main_bot.sent_messages[-1].text.splitlines()
    assert error_bot.sent_messages == []
    assert repository.get(1001).flow == "idle"


def test_decline_consent_requires_confirmation(tmp_path: Path) -> None:
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

    response = service.decline_consent(user, occurred_at=NOW)

    assert response.text == CONSENT_DECLINE_CONFIRM_TEXT
    assert response.buttons == (CONSENT_DECLINE_RECONSIDER_BUTTON, CONSENT_DECLINE_CONFIRM_BUTTON)
    assert main_bot.sent_messages[-1].text == CONSENT_DECLINE_CONFIRM_TEXT
    assert error_bot.sent_messages == []
    assert repository.get(1001).step == "awaiting_consent_decline_confirmation"


def test_confirm_consent_decline_updates_sheets(tmp_path: Path) -> None:
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

    response = service.confirm_consent_decline(user, occurred_at=NOW)

    participant = gateway.find_participant_by_telegram_id(1001)
    assert response.text == CONSENT_DECLINED_TEXT
    assert participant["consent_given"] is False
    assert participant["consent_status"] == "declined"
    assert participant["participant_stage"] == "declined"
    assert main_bot.sent_messages[-1].text == CONSENT_DECLINED_TEXT
    assert error_bot.sent_messages == []
    assert repository.get(1001).step == "declined"


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


def test_unknown_user_can_start_registration_during_active_flow_window(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        challenge_flows=[_active_flow()],
    )

    response = service.handle_start(
        TelegramUserContext(telegram_id=404, chat_id="chat-404"),
        occurred_at=REGISTRATION_NOW,
    )

    assert "Смерть иллюзий" in main_bot.sent_messages[0].text
    assert response.text == CONSENT_TEXT
    assert repository.get(404) is None
    assert error_bot.sent_messages == []


def test_unknown_user_is_rejected_after_registration_window(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        challenge_flows=[_active_flow()],
    )

    response = service.handle_start(
        TelegramUserContext(telegram_id=404, chat_id="chat-404"),
        occurred_at=REGISTRATION_CLOSED,
    )

    assert response.text == "Данный поток уже набран"
    assert main_bot.sent_messages[-1].text == "Данный поток уже набран"
    assert repository.get(404) is None
    assert error_bot.sent_messages == []


def test_registration_collects_name_and_creates_participant_after_confirmation(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        participants=[
            {
                "flow_id": "FLOW_2",
                "participant_id": "C001",
                "telegram_id": 1001,
                "first_name": "Анна",
                "last_name": "Иванова",
                "full_name": "Анна Иванова",
                "role": "captain",
                "team_id": "T001",
                "team_name": "Команда 1",
                "status": "active",
                "consent_given": True,
            }
        ],
        teams=[{"flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1", "captain_id": "C001", "is_active": True}],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404", username="new-user")

    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    consent = service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    assert consent.text == "Как тебя зовут? Напиши только имя."
    surname = service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    assert surname.text == "Напиши фамилию."
    captain = service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    assert captain.text == "Выбери капитана своей команды."
    assert captain.buttons[0].text == "Анна Иванова"

    confirmation = service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    assert "Пётр Петров" in confirmation.text
    assert "Анна Иванова" in confirmation.text
    completed = service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    participant = gateway.find_participant_by_telegram_id(404)
    assert participant is not None
    assert participant["flow_id"] == "FLOW_2"
    assert participant["first_name"] == "Пётр"
    assert participant["last_name"] == "Петров"
    assert participant["team_id"] == "T001"
    assert participant["captain_id"] == "C001"
    assert participant["consent_given"] is True
    assert "успешно зарегистрирован" in completed.text
    assert repository.get(404).flow == "idle"
    assert error_bot.sent_messages == []


def test_repeated_start_resumes_registration_without_duplicate(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")

    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    resumed = service.handle_start(user, occurred_at=REGISTRATION_NOW)

    assert resumed.text == "Как тебя зовут? Напиши только имя."
    assert repository.get(404).step == "awaiting_first_name"
    assert gateway.find_participant_by_telegram_id(404) is None


def test_registration_window_includes_exact_open_and_close_boundaries(tmp_path: Path) -> None:
    for index, occurred_at in enumerate((REGISTRATION_OPEN, "2026-09-16T18:00:00+05:00"), start=1):
        service, _gateway, _main_bot, error_bot, _notification_bot, _repository = _build_service(
            tmp_path / str(index),
            challenge_flows=[_active_flow()],
        )
        response = service.handle_start(
            TelegramUserContext(telegram_id=400 + index, chat_id=f"chat-{index}"),
            occurred_at=occurred_at,
        )
        assert response.text == CONSENT_TEXT
        assert error_bot.sent_messages == []


def test_registration_draft_cannot_cross_into_another_active_flow(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    gateway._challenge_flows[0]["flow_status"] = "completed"
    gateway._challenge_flows.append({**_active_flow(), "flow_id": "FLOW_3"})

    response = service.handle_start(user, occurred_at=REGISTRATION_NOW)

    assert response.text == CONSENT_TEXT
    assert repository.get(404) is None


def test_registration_rejects_captain_without_authoritative_active_team(tmp_path: Path) -> None:
    service, _gateway, _main_bot, error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{"flow_id": "FLOW_2", "team_id": "T001", "captain_id": "C999", "is_active": True}],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)

    response = service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)

    assert response.text == "Регистрация временно недоступна. Сообщи администратору."
    assert len(error_bot.sent_messages) >= 1


def test_editing_registration_name_requires_new_value_before_confirmation(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{"flow_id": "FLOW_2", "team_id": "T001", "captain_id": "C001", "is_active": True}],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)

    response = service.edit_registration_name(user, field="first_name", occurred_at=REGISTRATION_NOW)
    resumed = service.handle_start(user, occurred_at=REGISTRATION_NOW)

    assert response.text == "Как тебя зовут? Напиши только имя."
    assert resumed.text == "Как тебя зовут? Напиши только имя."
    assert repository.get(404).step == "awaiting_first_name"


def _build_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]] | None = None,
    teams: list[dict[str, object]] | None = None,
    challenge_flows: list[dict[str, object]] | None = None,
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
    gateway = FakeSheetsGateway(
        participants=participants or [],
        teams=teams or [],
        challenge_flows=challenge_flows or [],
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
    repository = DialogStateRepository(db_path)
    return (
        ParticipantFlowService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            dialog_states=repository,
            registration_flows=gateway,
            registration_drafts=RegistrationDraftRepository(db_path),
        ),
        gateway,
        main_bot,
        error_bot,
        notification_bot,
        repository,
    )


def _active_flow() -> dict[str, object]:
    return {
        "flow_id": "FLOW_2",
        "flow_name": "Поток 2",
        "flow_status": "active",
        "kickoff_meeting_at": REGISTRATION_OPEN,
        "registration_opens_at": REGISTRATION_OPEN,
        "registration_closes_at": "2026-09-16T18:00:00+05:00",
        "goal_setup_start_date": "2026-09-09",
        "goal_setup_end_date": "2026-09-13",
        "steps_setup_start_date": "2026-09-14",
        "steps_setup_end_date": "2026-09-20",
        "week_01_start_date": "2026-09-21",
        "week_08_end_date": "2026-11-15",
    }
