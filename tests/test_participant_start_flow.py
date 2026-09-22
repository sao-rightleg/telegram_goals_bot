from pathlib import Path

import pytest

from app.errors import ActionDiagnosticError, ActionDiagnosticKind

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
from app.sheets.gateway import FakeSheetsGateway, GoogleSheetsError
from app.storage.dialog_state import DialogStateRepository
from app.storage.goal_drafts import GoalDraftRepository
from app.storage.registration import RegistrationDraftRepository
from app.storage.sqlite import initialize_schema
from app.storage.step_drafts import StepDraftRepository


REGISTRATION_OPEN = "2026-09-09T18:00:00+05:00"
REGISTRATION_NOW = "2026-09-10T10:00:00+05:00"
REGISTRATION_CLOSED = "2026-09-16T18:00:01+05:00"


NOW = "2026-07-02T10:00:00+05:00"


def test_participant_creates_confirmed_goal_in_google_sheets_boundary(tmp_path: Path) -> None:
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P001", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active", "consent_given": True,
    }
    service, gateway, _main_bot, _error_bot, _notification_bot, repository = _build_service(
        tmp_path, participants=[participant], challenge_flows=[_active_flow()]
    )
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    start = service.handle_menu_action(user, "view_goal", occurred_at=REGISTRATION_NOW)
    assert "Кратко напиши цель" in start.text
    prompts = []
    for value in (
        "Запустить новое направление",
        "Получить первые оплаченные заказы",
        "3",
        "клиента",
        "Подписаны договоры и получена оплата от трёх клиентов",
    ):
        prompts.append(service.handle_goal_text(user, value, occurred_at=REGISTRATION_NOW).text)
    assert prompts[-1] == (
        "Проверь цель перед сохранением:\n\n"
        "Цель: Запустить новое направление\n"
        "Результат: Получить первые оплаченные заказы\n"
        "Значение: 3 клиента\n"
        "Условие достижения: Подписаны договоры и получена оплата от трёх клиентов"
    )

    response = service.confirm_goal(user, occurred_at=REGISTRATION_NOW)

    assert response.text == "Цель сохранена."
    goal = gateway.get_active_goal("P001")
    assert goal is not None
    assert {key: goal[key] for key in (
        "flow_id", "participant_id", "team_id", "goal_title", "goal_description",
        "goal_value_amount", "goal_value_currency", "permission_condition", "goal_status",
    )} == {
        "flow_id": "FLOW_2", "participant_id": "P001", "team_id": "T001",
        "goal_title": "Запустить новое направление",
        "goal_description": "Получить первые оплаченные заказы",
        "goal_value_amount": "3", "goal_value_currency": "клиента",
        "permission_condition": "Подписаны договоры и получена оплата от трёх клиентов",
        "goal_status": "active",
    }
    assert repository.get(1001).flow == "idle"


@pytest.mark.parametrize(
    ("onboarding_at", "occurred_at"),
    [
        ("2026-09-14T00:00:00+05:00", "2026-09-14T00:00:00+05:00"),
        ("2026-09-20T23:36:38+05:00", "2026-09-21T10:00:00+05:00"),
        ("2026-09-20T23:36:38+05:00", "2026-09-26T00:00:00+05:00"),
    ],
)
def test_late_registered_participant_can_create_goal_until_registration_closes(
    tmp_path: Path, onboarding_at: str, occurred_at: str,
) -> None:
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P0EEA0473014F", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active",
        "consent_given": True,
        "created_at": onboarding_at,
        "onboarding_completed_at": onboarding_at,
    }
    flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, *_ = _build_service(
        tmp_path, participants=[participant], challenge_flows=[flow],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "captain_id": "C001",
            "is_active": True,
        }],
    )

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        "view_goal",
        occurred_at=occurred_at,
    )

    assert "Кратко напиши цель" in response.text


@pytest.mark.parametrize(
    ("onboarding_completed_at", "occurred_at"),
    [
        ("2026-09-10T10:00:00+05:00", "2026-09-21T10:00:00+05:00"),
        ("2026-09-20T23:36:38+05:00", "2026-09-26T00:00:01+05:00"),
    ],
)
def test_goal_deadline_is_not_extended_for_existing_or_too_late_participant(
    tmp_path: Path, onboarding_completed_at: str, occurred_at: str,
) -> None:
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P0EEA0473014F", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active",
        "consent_given": True, "created_at": onboarding_completed_at,
        "onboarding_completed_at": onboarding_completed_at,
    }
    flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, *_ = _build_service(
        tmp_path, participants=[participant], challenge_flows=[flow]
    )

    with pytest.raises(ActionDiagnosticError, match="Goal setup stage is not active") as exc_info:
        service.handle_menu_action(
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
            "view_goal",
            occurred_at=occurred_at,
        )
    assert exc_info.value.kind is ActionDiagnosticKind.GOAL_STAGE_CLOSED


def test_goal_diagnostic_distinguishes_missing_flow_from_closed_stage(tmp_path: Path) -> None:
    service, *_ = _build_service(tmp_path)

    with pytest.raises(ActionDiagnosticError) as exc_info:
        service._eligible_goal_participant(
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
            occurred_at="2026-09-12T10:00:00+05:00",
        )

    assert exc_info.value.kind is ActionDiagnosticKind.GOAL_FLOW_UNAVAILABLE
    assert exc_info.value.reason == "flow_unavailable"


def test_existing_participant_cannot_gain_late_mode_by_accepting_consent_late(
    tmp_path: Path,
) -> None:
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P0EEA0473014F", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active",
        "consent_given": True, "created_at": "2026-09-09T10:00:00+05:00",
        "onboarding_completed_at": "2026-09-21T10:00:00+05:00",
    }
    flow = {
        **_active_flow(), "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, *_ = _build_service(
        tmp_path, participants=[participant], challenge_flows=[flow]
    )

    with pytest.raises(ActionDiagnosticError, match="Goal setup stage is not active") as exc_info:
        service.handle_menu_action(
            TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
            "view_goal", occurred_at="2026-09-21T10:00:01+05:00",
        )
    assert exc_info.value.kind is ActionDiagnosticKind.GOAL_STAGE_CLOSED


def test_goal_creation_does_not_create_second_active_goal(tmp_path: Path) -> None:
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P0EEA0473014F", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active", "consent_given": True,
    }
    service, gateway, *_ = _build_service(
        tmp_path, participants=[participant], challenge_flows=[_active_flow()]
    )
    gateway.append_goal({"goal_id": "G001", "participant_id": "P001", "goal_status": "active"})
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    response = service.handle_menu_action(user, "view_goal", occurred_at=REGISTRATION_NOW)

    assert "G001" not in response.text
    assert len(gateway.list_goals()) == 1


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


def test_repeat_start_does_not_write_bot_started_timestamp_again(tmp_path: Path) -> None:
    service, gateway, *_ = _build_service(
        tmp_path,
        participants=[
            {
                "participant_id": "P001",
                "telegram_id": 1001,
                "role": "participant",
                "consent_given": True,
                "bot_started_at": NOW,
            }
        ],
    )
    writes = 0
    original = gateway.mark_participant_bot_started

    def count_write(participant_id: str, *, started_at: str) -> None:
        nonlocal writes
        writes += 1
        original(participant_id, started_at=started_at)

    gateway.mark_participant_bot_started = count_write

    service.handle_start(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        occurred_at="2026-07-03T10:00:00+05:00",
    )

    assert writes == 0


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
                "team_name": "Устаревшее название в Participants",
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
    assert captain.text == "Выбери свою команду."
    assert captain.buttons[0].text == "Команда 1"

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
    assert completed.text == "\n".join(
        (
            "Пётр, ты успешно зарегистрирован в проекте «Смерть иллюзий».",
            "",
            "Твой капитан — Анна Иванова.",
            "Твоя команда — Команда 1.",
            "",
            "Краткое расписание:",
            "",
            "Постановка цели:",
            "09.09.2026–16.09.2026",
            "",
            "Формирование шагов:",
            "14.09.2026–20.09.2026",
            "",
            "Рабочие недели:",
            "",
            "Неделя 1: 21.09.2026–27.09.2026",
            "Неделя 2: 28.09.2026–04.10.2026",
            "Неделя 3: 05.10.2026–11.10.2026",
            "Неделя 4: 12.10.2026–18.10.2026",
            "Неделя 5: 19.10.2026–25.10.2026",
            "Неделя 6: 26.10.2026–01.11.2026",
            "Неделя 7: 02.11.2026–08.11.2026",
            "Неделя 8: 09.11.2026–15.11.2026",
            "",
            "🎓 Выпускной: 15.11.2026",
        )
    )
    assert repository.get(404).flow == "idle"
    assert error_bot.sent_messages == []


def test_captain_can_register_first_from_authoritative_team_assignment(tmp_path: Path) -> None:
    service, gateway, _main_bot, error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Новая команда",
            "captain_id": "C009", "captain_telegram_id": 404, "is_active": True,
        }],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404", username="captain-new")

    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Гульфия", occurred_at=REGISTRATION_NOW)
    confirmation = service.handle_registration_text(
        user, "Хасанова", occurred_at=REGISTRATION_NOW
    )

    assert confirmation.text == (
        "Проверь данные:\n\n"
        "Имя и фамилия: Гульфия Хасанова\n"
        "Капитан: Гульфия Хасанова\n"
        "Команда: Новая команда"
    )
    assert [button.callback_data for button in confirmation.buttons] == [
        "registration:confirm",
        "registration:edit_first_name",
        "registration:edit_last_name",
    ]

    resumed = service.handle_start(user, occurred_at=REGISTRATION_NOW)
    assert resumed.text == confirmation.text
    assert [button.callback_data for button in resumed.buttons] == [
        "registration:confirm",
        "registration:edit_first_name",
        "registration:edit_last_name",
    ]

    completed = service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    captain = gateway.find_participant_in_flow("FLOW_2", 404)
    assert captain is not None
    assert {
        key: captain[key]
        for key in ("participant_id", "role", "team_id", "team_name", "captain_id")
    } == {
        "participant_id": "C009",
        "role": "captain",
        "team_id": "T009",
        "team_name": "Новая команда",
        "captain_id": "C009",
    }
    assert "Твой капитан — Гульфия Хасанова." in completed.text
    assert "Твоя команда — Новая команда." in completed.text
    assert repository.get(404).flow == "idle"
    assert error_bot.sent_messages == []


def test_registered_first_captain_appears_for_later_participants(tmp_path: Path) -> None:
    team = {
        "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Новая команда",
        "captain_id": "C009", "captain_telegram_id": 404, "is_active": True,
    }
    service, gateway, *_ = _build_service(
        tmp_path, teams=[team], challenge_flows=[_active_flow()]
    )
    captain = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(captain, occurred_at=REGISTRATION_NOW)
    service.accept_consent(captain, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(captain, "Гульфия", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(captain, "Хасанова", occurred_at=REGISTRATION_NOW)
    service.confirm_registration(captain, occurred_at=REGISTRATION_NOW)

    participant = TelegramUserContext(telegram_id=405, chat_id="chat-405")
    service.handle_start(participant, occurred_at=REGISTRATION_NOW)
    service.accept_consent(participant, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(participant, "Анна", occurred_at=REGISTRATION_NOW)
    selection = service.handle_registration_text(
        participant, "Петрова", occurred_at=REGISTRATION_NOW
    )

    assert [(button.text, button.callback_data) for button in selection.buttons] == [
        ("Новая команда", "registration:captain:C009")
    ]
    service.select_registration_captain(
        participant, captain_id="C009", occurred_at=REGISTRATION_NOW
    )
    service.confirm_registration(participant, occurred_at=REGISTRATION_NOW)

    saved = gateway.find_participant_in_flow("FLOW_2", 405)
    assert saved is not None
    assert {
        key: saved[key]
        for key in ("role", "team_id", "team_name", "captain_id")
    } == {
        "role": "participant",
        "team_id": "T009",
        "team_name": "Новая команда",
        "captain_id": "C009",
    }
    assert str(saved["participant_id"]).startswith("P")
    assert saved["participant_id"] != "C009"


def test_two_captains_register_for_one_team_and_participant_selects_team(
    tmp_path: Path,
) -> None:
    team = {
        "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Новая команда",
        "is_active": True,
    }
    assignments = [
        {
            "flow_id": "FLOW_2", "team_id": "T009", "captain_id": "C009",
            "captain_telegram_id": 404, "is_primary": True, "is_active": True,
        },
        {
            "flow_id": "FLOW_2", "team_id": "T009", "captain_id": "C010",
            "captain_telegram_id": 410, "is_primary": False, "is_active": True,
        },
    ]
    service, gateway, *_ = _build_service(
        tmp_path, teams=[team], team_captains=assignments,
        challenge_flows=[_active_flow()],
    )
    for telegram_id, first_name, last_name in (
        (404, "Гульфия", "Хасанова"),
        (410, "Антон", "Иванов"),
    ):
        user = TelegramUserContext(telegram_id=telegram_id, chat_id=f"chat-{telegram_id}")
        service.handle_start(user, occurred_at=REGISTRATION_NOW)
        service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
        service.handle_registration_text(user, first_name, occurred_at=REGISTRATION_NOW)
        confirmation = service.handle_registration_text(
            user, last_name, occurred_at=REGISTRATION_NOW
        )
        assert "Команда: Новая команда" in confirmation.text
        service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    primary = gateway.find_participant_in_flow("FLOW_2", 404)
    secondary = gateway.find_participant_in_flow("FLOW_2", 410)
    assert primary is not None and secondary is not None
    assert (primary["participant_id"], primary["role"], primary["captain_id"]) == (
        "C009", "captain", "C009",
    )
    assert (secondary["participant_id"], secondary["role"], secondary["captain_id"]) == (
        "C010", "captain", "C009",
    )

    participant = TelegramUserContext(telegram_id=420, chat_id="chat-420")
    service.handle_start(participant, occurred_at=REGISTRATION_NOW)
    service.accept_consent(participant, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(participant, "Мария", occurred_at=REGISTRATION_NOW)
    selection = service.handle_registration_text(
        participant, "Петрова", occurred_at=REGISTRATION_NOW
    )
    assert [(button.text, button.callback_data) for button in selection.buttons] == [
        ("Новая команда", "registration:captain:C009")
    ]
    confirmation = service.select_registration_captain(
        participant, captain_id="C009", occurred_at=REGISTRATION_NOW
    )
    assert "Капитаны: Гульфия Хасанова, Антон Иванов" in confirmation.text
    completed = service.confirm_registration(participant, occurred_at=REGISTRATION_NOW)
    assert "Твои капитаны — Гульфия Хасанова, Антон Иванов." in completed.text


def test_participant_registration_fails_closed_when_team_has_two_primary_captains(
    tmp_path: Path,
) -> None:
    captains = [
        {
            "flow_id": "FLOW_2", "participant_id": captain_id,
            "telegram_id": telegram_id, "first_name": name, "last_name": "Капитан",
            "full_name": f"{name} Капитан", "role": "captain", "team_id": "T009",
            "status": "active", "consent_given": True,
        }
        for captain_id, telegram_id, name in (
            ("C009", 404, "Первый"), ("C010", 410, "Второй")
        )
    ]
    service, gateway, _main_bot, error_bot, *_ = _build_service(
        tmp_path,
        participants=captains,
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T009",
            "team_name": "Новая команда", "is_active": True,
        }],
        team_captains=[
            {
                "flow_id": "FLOW_2", "team_id": "T009", "captain_id": "C009",
                "captain_telegram_id": 404, "is_primary": True, "is_active": True,
            },
            {
                "flow_id": "FLOW_2", "team_id": "T009", "captain_id": "C010",
                "captain_telegram_id": 410, "is_primary": True, "is_active": True,
            },
        ],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=420, chat_id="chat-420")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Мария", occurred_at=REGISTRATION_NOW)

    response = service.handle_registration_text(
        user, "Петрова", occurred_at=REGISTRATION_NOW
    )

    assert response.text == "Регистрация временно недоступна. Сообщи администратору."
    assert gateway.find_participant_in_flow("FLOW_2", 420) is None
    assert len(error_bot.sent_messages) == 1


def test_late_first_captain_continues_to_goal_and_eight_steps(tmp_path: Path) -> None:
    late_now = "2026-09-21T10:00:00+05:00"
    flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, gateway, main_bot, _error_bot, _notification_bot, repository = _build_service(
        tmp_path,
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Новая команда",
            "captain_id": "C009", "captain_telegram_id": "404", "is_active": True,
        }],
        challenge_flows=[flow],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=late_now)
    service.accept_consent(user, consent_given_at=late_now)
    service.handle_registration_text(user, "Гульфия", occurred_at=late_now)
    service.handle_registration_text(user, "Хасанова", occurred_at=late_now)

    goal_prompt = service.confirm_registration(user, occurred_at=late_now)

    assert "Кратко напиши цель" in goal_prompt.text
    assert "успешно зарегистрирован" in main_bot.sent_messages[-2].text
    captain = gateway.find_participant_in_flow("FLOW_2", 404)
    assert captain is not None
    assert captain["role"] == "captain"

    for value in ("Новая цель", "Получить результат", "10", "клиентов", "Есть результат"):
        service.handle_goal_text(user, value, occurred_at=late_now)
    steps_prompt = service.confirm_goal(user, occurred_at=late_now)

    assert steps_prompt.text.startswith("Сформулируем 8 шагов")
    for number in range(1, 9):
        service.handle_steps_text(user, f"Шаг капитана {number}", occurred_at=late_now)
        service.handle_steps_text(user, f"Метрика капитана {number}", occurred_at=late_now)

    completed = service.confirm_steps(user, occurred_at=late_now)

    goal = gateway.get_active_goal("C009")
    assert goal is not None
    steps = gateway.list_planned_steps("C009", str(goal["goal_id"]))
    assert [step["step_number"] for step in steps] == list(range(1, 9))
    assert [step["step_title"] for step in steps] == [
        f"Шаг капитана {number}" for number in range(1, 9)
    ]
    assert [step["step_metric"] for step in steps] == [
        f"Метрика капитана {number}" for number in range(1, 9)
    ]
    assert all(step["participant_id"] == "C009" for step in steps)
    assert all(step["goal_id"] == goal["goal_id"] for step in steps)
    assert completed.text == "Восемь шагов сохранены."
    assert repository.get(404).flow == "idle"
    assert repository.get(404).step == "steps_saved"


def test_captain_registration_fails_closed_for_duplicate_active_team_assignments(
    tmp_path: Path,
) -> None:
    service, gateway, _main_bot, error_bot, *_ = _build_service(
        tmp_path,
        teams=[
            {
                "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Команда 9",
                "captain_id": "C009", "captain_telegram_id": 404, "is_active": True,
            },
            {
                "flow_id": "FLOW_2", "team_id": "T010", "team_name": "Команда 10",
                "captain_id": "C010", "captain_telegram_id": 404, "is_active": True,
            },
        ],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Гульфия", occurred_at=REGISTRATION_NOW)

    response = service.handle_registration_text(
        user, "Хасанова", occurred_at=REGISTRATION_NOW
    )

    assert response.text == "Регистрация временно недоступна. Сообщи администратору."
    assert gateway.find_participant_in_flow("FLOW_2", 404) is None
    assert len(error_bot.sent_messages) == 1


def test_captain_registration_rejects_reused_captain_id(tmp_path: Path) -> None:
    service, gateway, _main_bot, error_bot, *_ = _build_service(
        tmp_path,
        teams=[
            {
                "flow_id": "FLOW_2", "team_id": "T009", "team_name": "Команда 9",
                "captain_id": "C009", "captain_telegram_id": 404, "is_active": True,
            },
            {
                "flow_id": "FLOW_2", "team_id": "T010", "team_name": "Команда 10",
                "captain_id": "C009", "captain_telegram_id": 410, "is_active": True,
            },
        ],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Гульфия", occurred_at=REGISTRATION_NOW)

    response = service.handle_registration_text(
        user, "Хасанова", occurred_at=REGISTRATION_NOW
    )

    assert response.text == "Регистрация временно недоступна. Сообщи администратору."
    assert gateway.find_participant_in_flow("FLOW_2", 404) is None
    assert len(error_bot.sent_messages) == 1


def test_late_registration_continues_directly_to_goal_and_then_steps(tmp_path: Path) -> None:
    flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, gateway, main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[flow],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    late_now = "2026-09-21T10:00:00+05:00"
    service.handle_start(user, occurred_at=late_now)
    service.accept_consent(user, consent_given_at=late_now)
    service.handle_registration_text(user, "Пётр", occurred_at=late_now)
    service.handle_registration_text(user, "Петров", occurred_at=late_now)
    service.select_registration_captain(user, captain_id="C001", occurred_at=late_now)

    goal_prompt = service.confirm_registration(user, occurred_at=late_now)

    assert "Кратко напиши цель" in goal_prompt.text
    assert "успешно зарегистрирован" in main_bot.sent_messages[-2].text
    participant = gateway.find_participant_by_telegram_id(404)
    assert participant is not None
    assert participant["onboarding_completed_at"] == late_now

    for value in (
        "Новая цель", "Получить результат", "10", "клиентов", "Заключены договоры",
    ):
        service.handle_goal_text(user, value, occurred_at=late_now)

    steps_prompt = service.confirm_goal(user, occurred_at=late_now)

    assert gateway.get_active_goal(str(participant["participant_id"])) is not None
    assert main_bot.sent_messages[-2].text == "Цель сохранена."
    assert steps_prompt.text.startswith("Сформулируем 8 шагов")


def test_late_onboarding_retry_resumes_after_persisted_participant_and_goal(
    tmp_path: Path,
) -> None:
    late_now = "2026-09-21T10:00:00+05:00"
    participant = {
        "flow_id": "FLOW_2", "participant_id": "P0EEA0473014F", "telegram_id": 1001,
        "team_id": "T001", "role": "participant", "status": "active",
        "consent_given": True, "created_at": late_now,
        "onboarding_completed_at": late_now,
    }
    flow = {
        **_active_flow(), "registration_closes_at": "2026-09-26T00:00:00+05:00",
        "goal_setup_end_date": "2026-09-13",
    }
    service, gateway, *_ = _build_service(
        tmp_path, participants=[participant], challenge_flows=[flow],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "captain_id": "C001",
            "is_active": True,
        }],
    )
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")

    goal_retry = service.confirm_registration(user, occurred_at=late_now)
    assert "Кратко напиши цель" in goal_retry.text

    gateway.append_goal({
        "flow_id": "FLOW_2", "goal_id": "G001", "participant_id": "P0EEA0473014F",
        "team_id": "T001", "goal_status": "active",
    })
    steps_retry = service.confirm_goal(user, occurred_at=late_now)

    assert steps_retry.text.startswith("Сформулируем 8 шагов")


def test_registration_loads_participants_and_teams_once_for_captain_buttons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captains = [
        {
            "flow_id": "FLOW_2", "participant_id": captain_id,
            "full_name": full_name, "role": "captain", "team_id": team_id,
            "status": "active", "consent_given": True,
        }
        for captain_id, full_name, team_id in (
            ("C001", "Анна Иванова", "T001"),
            ("C002", "Борис Петров", "T002"),
        )
    ]
    captains.extend(
        (
            {
                "flow_id": "FLOW_2", "participant_id": "C003", "full_name": "Неактивный",
                "role": "captain", "team_id": "T003", "status": "dropped", "consent_given": True,
            },
            {
                "flow_id": "FLOW_2", "participant_id": "C004", "full_name": "Без согласия",
                "role": "captain", "team_id": "T004", "status": "active", "consent_given": False,
            },
            {
                "flow_id": "FLOW_2", "participant_id": "C005", "full_name": "Чужая команда",
                "role": "captain", "team_id": "T005", "status": "active", "consent_given": True,
            },
        )
    )
    teams = [
        {
            "flow_id": "FLOW_2", "team_id": team_id, "captain_id": captain_id,
            "is_active": True,
        }
        for team_id, captain_id in (("T001", "C001"), ("T002", "C002"))
    ]
    teams.append({
        "flow_id": "FLOW_2", "team_id": "T999", "captain_id": "C001",
        "is_active": True,
    })
    teams.extend(
        (
            {"flow_id": "FLOW_2", "team_id": "T003", "captain_id": "C003", "is_active": True},
            {"flow_id": "FLOW_2", "team_id": "T004", "captain_id": "C004", "is_active": True},
            {"flow_id": "FLOW_2", "team_id": "T999", "captain_id": "C005", "is_active": True},
        )
    )
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=captains,
        teams=teams,
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    calls = {"participants": 0, "teams": 0, "participant": 0}
    original_list_participants = gateway.list_participants
    original_list_teams = gateway.list_teams
    original_get_participant = gateway.get_participant

    def list_participants() -> list[dict[str, object]]:
        calls["participants"] += 1
        return original_list_participants()

    def list_teams() -> list[dict[str, object]]:
        calls["teams"] += 1
        return original_list_teams()

    def get_participant(participant_id: str) -> dict[str, object] | None:
        calls["participant"] += 1
        return original_get_participant(participant_id)

    monkeypatch.setattr(gateway, "list_participants", list_participants)
    monkeypatch.setattr(gateway, "list_teams", list_teams)
    monkeypatch.setattr(gateway, "get_participant", get_participant)

    response = service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)

    assert [(button.text, button.callback_data) for button in response.buttons] == [
        ("Команда", "registration:captain:C001"),
        ("Команда", "registration:captain:C002"),
    ]
    assert calls == {"participants": 1, "teams": 1, "participant": 0}


@pytest.mark.parametrize(
    ("flow_change", "error_match"),
    [
        ({"week_08_end_date": "2026-11-14"}, "eight consecutive"),
        ({"steps_setup_start_date": "2026-09-08"}, "phases are inconsistent"),
        ({"goal_setup_start_date": "2026-09-17"}, "phases are inconsistent"),
        (
            {"week_01_start_date": "2026-09-22", "week_08_end_date": "2026-11-16"},
            "phases are inconsistent",
        ),
        (
            {
                "goal_setup_end_date": "2026-09-20",
                "steps_setup_start_date": "2026-09-21",
                "steps_setup_end_date": "2026-09-19",
                "week_01_start_date": "2026-09-20",
                "week_08_end_date": "2026-11-14",
            },
            "phases are inconsistent",
        ),
        ({"goal_setup_end_date": "not-a-date"}, "Invalid isoformat"),
        ({"week_01_start_date": ""}, "schedule is incomplete"),
    ],
)
def test_registration_calendar_failure_happens_before_participant_append(
    tmp_path: Path,
    flow_change: dict[str, object],
    error_match: str,
) -> None:
    flow = {**_active_flow(), **flow_change}
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[flow],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)

    with pytest.raises(ValueError, match=error_match):
        service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    assert gateway.find_participant_by_telegram_id(404) is None


def test_registration_rechecks_authoritative_team_before_append(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "team_name": "Устаревшее название", "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    gateway._teams[0]["is_active"] = False

    response = service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    assert response.text == "Регистрация временно недоступна. Сообщи администратору."
    assert gateway.find_participant_by_telegram_id(404) is None


def test_registration_does_not_mix_flows_when_active_flow_switches_during_confirmation(
    tmp_path: Path,
) -> None:
    old_flow = _active_flow()
    new_flow = {**_active_flow(), "flow_id": "FLOW_3"}
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[old_flow],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    active_flow_reads = 0

    def switching_active_flow() -> dict[str, object]:
        nonlocal active_flow_reads
        active_flow_reads += 1
        return old_flow if active_flow_reads <= 2 else new_flow

    gateway.get_active_challenge_flow = switching_active_flow

    response = service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    assert response.text == CONSENT_TEXT
    assert gateway.find_participant_by_telegram_id(404) is None


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


def test_start_cleans_stale_registration_after_participant_was_written(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, dialog_states = _build_service(
        tmp_path,
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    drafts = RegistrationDraftRepository(tmp_path / "state.sqlite3")
    draft = drafts.get(404)
    assert draft is not None
    assert drafts.claim_finalization(
        404,
        claim_token="interrupted-worker",
        updated_at=REGISTRATION_NOW,
        stale_before="2026-09-10T09:00:00+05:00",
    )
    gateway.append_participant({
        "flow_id": "FLOW_2", "participant_id": "P404", "telegram_id": 404,
        "role": "participant", "status": "active", "consent_given": True,
    })

    response = service.handle_start(user, occurred_at="2026-09-10T10:01:00+05:00")

    assert response.menu_items
    assert drafts.get(404) is None
    state = dialog_states.get(404)
    assert state is not None
    assert (state.flow, state.step) == ("idle", "menu")


def test_registration_releases_claim_when_post_write_read_fails(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    append_finished = False
    original_append = gateway.append_participant
    original_find = gateway.find_participant_in_flow

    def append_then_mark(row: dict[str, object]) -> None:
        nonlocal append_finished
        original_append(row)
        append_finished = True

    def fail_first_read_after_append(flow_id: str, telegram_id: int) -> dict[str, object] | None:
        nonlocal append_finished
        if append_finished:
            append_finished = False
            raise GoogleSheetsError("temporary post-write read failure")
        return original_find(flow_id, telegram_id)

    gateway.append_participant = append_then_mark
    gateway.find_participant_in_flow = fail_first_read_after_append

    with pytest.raises(GoogleSheetsError):
        service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    draft = RegistrationDraftRepository(tmp_path / "state.sqlite3").get(404)
    assert draft is not None
    assert (draft.status, draft.claim_token) == ("active", None)
    assert gateway.find_participant_by_telegram_id(404) is not None

    response = service.handle_start(user, occurred_at="2026-09-10T10:01:00+05:00")
    assert response.menu_items
    assert RegistrationDraftRepository(tmp_path / "state.sqlite3").get(404) is None


@pytest.mark.parametrize("failure_mode", ["initial_read", "not_visible"])
def test_registration_releases_claim_for_every_verification_failure(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    original_find = gateway.find_participant_in_flow
    original_append = gateway.append_participant
    reads = 0
    append_finished = False

    def append_then_mark(row: dict[str, object]) -> None:
        nonlocal append_finished
        original_append(row)
        append_finished = True

    def fail_verification(flow_id: str, telegram_id: int) -> dict[str, object] | None:
        nonlocal reads, append_finished
        reads += 1
        if reads == 2 and failure_mode == "initial_read":
            raise GoogleSheetsError("initial verification read failed")
        if append_finished and failure_mode == "not_visible":
            append_finished = False
            return None
        return original_find(flow_id, telegram_id)

    gateway.append_participant = append_then_mark
    gateway.find_participant_in_flow = fail_verification

    expected_error = GoogleSheetsError if failure_mode == "initial_read" else RuntimeError
    with pytest.raises(expected_error):
        service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    draft = RegistrationDraftRepository(tmp_path / "state.sqlite3").get(404)
    assert draft is not None
    assert (draft.status, draft.claim_token) == ("active", None)


def test_registration_recovers_when_finalization_ownership_is_lost_after_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        participants=[{
            "flow_id": "FLOW_2", "participant_id": "C001", "telegram_id": 1001,
            "full_name": "Анна Иванова", "role": "captain", "team_id": "T001",
            "status": "active", "consent_given": True,
        }],
        teams=[{
            "flow_id": "FLOW_2", "team_id": "T001", "team_name": "Команда 1",
            "captain_id": "C001", "is_active": True,
        }],
        challenge_flows=[_active_flow()],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="chat-404")
    service.handle_start(user, occurred_at=REGISTRATION_NOW)
    service.accept_consent(user, consent_given_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Пётр", occurred_at=REGISTRATION_NOW)
    service.handle_registration_text(user, "Петров", occurred_at=REGISTRATION_NOW)
    service.select_registration_captain(user, captain_id="C001", occurred_at=REGISTRATION_NOW)
    assert service.registration_drafts is not None
    monkeypatch.setattr(service.registration_drafts, "complete_finalization", lambda *_args, **_kwargs: False)

    with pytest.raises(RuntimeError, match="ownership was lost"):
        service.confirm_registration(user, occurred_at=REGISTRATION_NOW)

    assert gateway.find_participant_by_telegram_id(404) is not None
    response = service.handle_start(user, occurred_at="2026-09-10T10:01:00+05:00")
    assert response.menu_items
    assert RegistrationDraftRepository(tmp_path / "state.sqlite3").get(404) is None


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


def test_admin_can_extend_registration_window_beyond_default_seven_days(tmp_path: Path) -> None:
    extended_flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T18:00:00+05:00",
    }
    service, _gateway, _main_bot, error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        challenge_flows=[extended_flow],
    )

    response = service.handle_start(
        TelegramUserContext(telegram_id=404, chat_id="chat-404"),
        occurred_at="2026-09-17T18:00:00+05:00",
    )

    assert response.text == CONSENT_TEXT
    assert error_bot.sent_messages == []


def test_registration_window_rejects_close_not_after_open(tmp_path: Path) -> None:
    invalid_flow = {
        **_active_flow(),
        "registration_closes_at": REGISTRATION_OPEN,
    }
    service, _gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        challenge_flows=[invalid_flow],
    )

    with pytest.raises(ValueError, match="Registration window must close after it opens"):
        service.handle_start(
            TelegramUserContext(telegram_id=404, chat_id="chat-404"),
            occurred_at=REGISTRATION_NOW,
        )


def test_registration_window_rejects_extension_beyond_ten_extra_days(tmp_path: Path) -> None:
    invalid_flow = {
        **_active_flow(),
        "registration_closes_at": "2026-09-26T18:00:01+05:00",
    }
    service, _gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        challenge_flows=[invalid_flow],
    )

    with pytest.raises(ValueError, match="Registration window cannot exceed seventeen days"):
        service.handle_start(
            TelegramUserContext(telegram_id=404, chat_id="chat-404"),
            occurred_at=REGISTRATION_NOW,
        )


def test_registration_window_must_open_at_kickoff(tmp_path: Path) -> None:
    invalid_flow = {
        **_active_flow(),
        "registration_opens_at": "2026-09-09T18:00:01+05:00",
    }
    service, _gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        challenge_flows=[invalid_flow],
    )

    with pytest.raises(ValueError, match="Registration window must start at kickoff"):
        service.handle_start(
            TelegramUserContext(telegram_id=404, chat_id="chat-404"),
            occurred_at=REGISTRATION_NOW,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kickoff_meeting_at", "2026-09-09T00:00:00+03:00"),
        ("registration_opens_at", "2026-09-09T00:00:00+03:00"),
        ("registration_closes_at", "2026-09-26T00:00:00+03:00"),
    ],
)
def test_registration_window_requires_yekaterinburg_offset_for_every_boundary(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    invalid_flow = {**_active_flow(), field: value}
    service, _gateway, _main_bot, _error_bot, _notification_bot, _repository = _build_service(
        tmp_path,
        challenge_flows=[invalid_flow],
    )

    with pytest.raises(
        ValueError,
        match="Registration window must use Asia/Yekaterinburg UTC offset",
    ):
        service.handle_start(
            TelegramUserContext(telegram_id=404, chat_id="chat-404"),
            occurred_at=REGISTRATION_NOW,
        )


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
    team_captains: list[dict[str, object]] | None = None,
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
        team_captains=team_captains or [],
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
            goal_drafts=GoalDraftRepository(db_path),
            step_drafts=StepDraftRepository(db_path),
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
        "goal_setup_end_date": "2026-09-16",
        "steps_setup_start_date": "2026-09-14",
        "steps_setup_end_date": "2026-09-20",
        "week_01_start_date": "2026-09-21",
        "week_08_end_date": "2026-11-15",
    }
