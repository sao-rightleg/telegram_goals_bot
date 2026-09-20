from datetime import datetime

import pytest

from app.bot.clients import BotPurpose, FakeBotClient, TelegramInlineButton
from app.bot.menus import (
    CAPTAIN_GOAL_CALLBACK_PREFIX,
    CAPTAIN_STEP_CALLBACK_PREFIX,
    CAPTAIN_STEPS_PAGE_CALLBACK_PREFIX,
)
from app.bot.messages import (
    CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT,
    CAPTAIN_GOAL_MISSING_TEXT,
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_PRIVATE_CHAT_ONLY_TEXT,
    CAPTAIN_STEPS_MISSING_TEXT,
    CAPTAIN_TEAM_TITLE_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_DECLINE_BUTTON,
    CONSENT_TEXT,
    MISSING_DATA_TEXT,
    UNKNOWN_USER_TEXT,
)
from app.scheduler.calendar import current_challenge_week_number
from app.services.captains import CaptainService, _format_step_score
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway


NOW = "2026-07-02T10:00:00+05:00"


def test_step_score_formatter_accepts_integer_zero_on_python_310() -> None:
    assert _format_step_score(0) == "0"
    assert _format_step_score(0.5) == "0.5"


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


def test_captain_can_view_live_progress_for_active_consented_own_team_only() -> None:
    week_number = current_challenge_week_number(datetime.fromisoformat(NOW))
    participants = [
        _participant("C001", 2001, role="captain", full_name="Капитан команды"),
        _participant("P001", 1001, full_name="Анна Своя"),
        _participant("P002", 1002, full_name="Борис Свой"),
        _participant("P003", 1003, team_id="T002", full_name="Олег Чужой"),
        _participant("P004", 1004, status="dropped", full_name="Выбывший Участник"),
        _participant("P005", 1005, consent_given=False, full_name="Без Согласия"),
    ]
    goals = [
        {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
        {"goal_id": "G003", "participant_id": "P003", "goal_status": "active"},
    ]
    planned_steps = [
        {
            "step_id": f"S{number}",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_number": number,
            "step_title": "Приоритетный шаг" if number == 3 else f"Шаг {number}",
            "step_status": "closed" if number <= 2 else "open",
        }
        for number in range(1, 9)
    ]
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=participants,
        goals=goals,
        planned_steps=planned_steps,
        weekly_focus=[
            {
                "focus_id": "WF001",
                "participant_id": "P001",
                "goal_id": "G001",
                "step_id": "S3",
                "week_number": week_number,
                "focus_status": "active",
            }
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == (
        "Прогресс команды на текущий момент\n\n"
        "Анна Своя\n"
        "Цель: 🟩\n"
        "Шаги: 🟩 8 из 8\n"
        "Фокус недели: «Приоритетный шаг»\n"
        "Выполнено: 2 из 8 — 25%\n"
        "🟩🟩⬜⬜⬜⬜⬜⬜\n\n"
        "Борис Свой\n"
        "Цель: ⬜\n"
        "Шаги: ⬜ 0 из 8\n"
        "Фокус недели: не выбран\n"
        "Выполнено: 0 из 8 — 0%\n"
        "⬜⬜⬜⬜⬜⬜⬜⬜\n\n"
        "Капитан команды\n"
        "Цель: ⬜\n"
        "Шаги: ⬜ 0 из 8\n"
        "Фокус недели: не выбран\n"
        "Выполнено: 0 из 8 — 0%\n"
        "⬜⬜⬜⬜⬜⬜⬜⬜"
    )
    assert "Олег Чужой" not in response.text
    assert "Выбывший Участник" not in response.text
    assert "Без Согласия" not in response.text
    assert main_bot.sent_messages[-1].text == response.text
    assert error_bot.sent_messages == []


def test_captain_can_choose_active_consented_own_team_member_to_view_goal() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан команды"),
            _participant("P001", 1001, full_name="Анна Своя"),
            _participant("P002", 1002, full_name="Борис Свой"),
            _participant("P003", 1003, team_id="T002", full_name="Олег Чужой"),
            _participant("P004", 1004, status="dropped", full_name="Выбывший"),
            _participant("P005", 1005, consent_given=False, full_name="Без Согласия"),
        ],
    )

    response = service.show_team_goals(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == "Выбери участника, чтобы посмотреть его цель."
    assert response.buttons == (
        TelegramInlineButton(text="Анна Своя", callback_data=f"{CAPTAIN_GOAL_CALLBACK_PREFIX}P001"),
        TelegramInlineButton(text="Борис Свой", callback_data=f"{CAPTAIN_GOAL_CALLBACK_PREFIX}P002"),
        TelegramInlineButton(text="Капитан команды", callback_data=f"{CAPTAIN_GOAL_CALLBACK_PREFIX}C001"),
    )
    assert main_bot.sent_messages[-1].buttons == response.buttons
    assert error_bot.sent_messages == []


def test_captain_can_view_full_active_goal_of_own_team_member() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан команды"),
            _participant("P001", 1001, full_name="Анна Своя"),
        ],
        goals=[{
            "goal_id": "G001",
            "participant_id": "P001",
            "goal_title": "Открыть новую студию",
            "goal_description": "Найти помещение и запустить продажи",
            "goal_value_amount": "1500000",
            "goal_value_currency": "RUB",
            "permission_condition": "Студия работает и принимает клиентов",
            "permission_metric_amount": "20",
            "permission_metric_unit": "клиентов",
            "goal_status": "active",
        }],
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == (
        "Цель участника: Анна Своя\n\n"
        "Цель: Открыть новую студию\n\n"
        "Описание: Найти помещение и запустить продажи\n\n"
        "Ценность: 1500000 RUB\n\n"
        "Условие разрешения: Студия работает и принимает клиентов\n\n"
        "Показатель выполнения: 20 клиентов"
    )
    assert main_bot.sent_messages[-1].text == response.text
    assert error_bot.sent_messages == []


def test_captain_can_choose_own_team_member_to_view_steps() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан команды"),
            _participant("P001", 1001, full_name="Анна Своя"),
            _participant("P002", 1002, team_id="T002", full_name="Олег Чужой"),
        ],
    )

    response = service.show_team_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == "Выбери участника, чтобы посмотреть его шаги."
    assert response.buttons == (
        TelegramInlineButton(text="Анна Своя", callback_data=f"{CAPTAIN_STEP_CALLBACK_PREFIX}P001"),
        TelegramInlineButton(text="Капитан команды", callback_data=f"{CAPTAIN_STEP_CALLBACK_PREFIX}C001"),
    )
    assert all("Олег" not in button.text for button in response.buttons)
    assert main_bot.sent_messages[-1].buttons == response.buttons
    assert error_bot.sent_messages == []


def test_captain_can_view_ordered_steps_of_participants_active_goal() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Анна Своя"),
        ],
        goals=[
            {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
            {"goal_id": "OLD", "participant_id": "P001", "goal_status": "closed"},
        ],
        planned_steps=[
            {"step_id": "S2", "participant_id": "P001", "goal_id": "G001", "step_number": 2, "step_title": "Второй шаг", "step_status": "closed"},
            {"step_id": "S1", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Первый шаг", "step_status": "open"},
            {"step_id": "OLD1", "participant_id": "P001", "goal_id": "OLD", "step_number": 1, "step_title": "Старый секретный шаг", "step_status": "open"},
        ],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == (
        "Шаги участника: Анна Своя\n\n"
        "1. ⬜ Первый шаг\n\n"
        "2. 🟩 Второй шаг"
    )
    assert "Старый секретный шаг" not in response.text
    assert main_bot.sent_messages[-1].text == response.text
    assert error_bot.sent_messages == []


@pytest.mark.parametrize("planned_steps", [[], [{"step_id": "OLD1", "participant_id": "P001", "goal_id": "OLD", "step_number": 1, "step_title": "Старый шаг", "step_status": "open"}]])
def test_captain_sees_missing_text_when_participant_has_no_active_steps(
    planned_steps: list[dict[str, object]],
) -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=planned_steps,
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_STEPS_MISSING_TEXT
    assert main_bot.sent_messages[-1].text == CAPTAIN_STEPS_MISSING_TEXT


def test_forged_steps_callback_cannot_reveal_another_team_steps() -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain"),
            _participant("P999", 9999, team_id="T002", full_name="Чужой участник"),
        ],
        goals=[{"goal_id": "G999", "participant_id": "P999", "goal_status": "active"}],
        planned_steps=[{"step_id": "S999", "participant_id": "P999", "goal_id": "G999", "step_number": 1, "step_title": "Секретный шаг", "step_status": "open"}],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P999",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT
    assert "Секретный шаг" not in response.text


@pytest.mark.parametrize("detail", [False, True])
def test_team_steps_are_not_disclosed_outside_captain_private_chat(detail: bool) -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=[{"step_id": "S001", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Секретный шаг", "step_status": "open"}],
    )
    user = TelegramUserContext(telegram_id=2001, chat_id="-100123")

    response = (
        service.show_participant_steps(user, participant_id="P001", now=datetime.fromisoformat(NOW))
        if detail
        else service.show_team_steps(user, now=datetime.fromisoformat(NOW))
    )

    assert response.text == CAPTAIN_PRIVATE_CHAT_ONLY_TEXT
    assert "Секретный шаг" not in response.text
    assert main_bot.sent_messages[-1].chat_id == "-100123"


@pytest.mark.parametrize(
    "captain_changes",
    [{"role": "participant"}, {"status": "inactive"}, {"consent_given": False}],
)
@pytest.mark.parametrize("detail", [False, True])
def test_team_steps_reject_ineligible_captain(
    captain_changes: dict[str, object],
    detail: bool,
) -> None:
    captain = _participant("C001", 2001, role="captain")
    captain.update(captain_changes)
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[captain, _participant("P001", 1001)],
    )

    user = TelegramUserContext(telegram_id=2001, chat_id="2001")
    response = (
        service.show_participant_steps(
            user,
            participant_id="P001",
            now=datetime.fromisoformat(NOW),
        )
        if detail
        else service.show_team_steps(user, now=datetime.fromisoformat(NOW))
    )

    expected = CONSENT_TEXT if captain_changes.get("consent_given") is False else CAPTAIN_ONLY_TEXT
    assert response.text == expected
    assert response.buttons == (
        (CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON)
        if expected == CONSENT_TEXT
        else ()
    )


def test_team_steps_list_uses_steps_pagination_prefix_and_exact_partition() -> None:
    participants = [_participant("C001", 2001, role="captain", full_name="Капитан")]
    participants.extend(
        _participant(f"P{index:03d}", 3000 + index, full_name=f"Участник {index:02d}")
        for index in range(1, 26)
    )
    participants.append(_participant("Я" * 60, 9999, full_name="Некорректный ID"))
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=participants,
    )
    user = TelegramUserContext(telegram_id=2001, chat_id="2001")

    first = service.show_team_steps(user, now=datetime.fromisoformat(NOW), page_index=0)
    second = service.show_team_steps(user, now=datetime.fromisoformat(NOW), page_index=1)
    negative = service.show_team_steps(user, now=datetime.fromisoformat(NOW), page_index=-1)
    oversized = service.show_team_steps(user, now=datetime.fromisoformat(NOW), page_index=999)

    first_members = [button for button in first.buttons if button.text != "Далее →"]
    second_members = [button for button in second.buttons if button.text != "← Назад"]
    assert len(first_members) == 20
    assert len(second_members) == 6
    assert first.buttons[-1].callback_data == f"{CAPTAIN_STEPS_PAGE_CALLBACK_PREFIX}1"
    assert second.buttons[0].callback_data == f"{CAPTAIN_STEPS_PAGE_CALLBACK_PREFIX}0"
    assert [button.callback_data for button in first_members + second_members] == [
        f"{CAPTAIN_STEP_CALLBACK_PREFIX}C001",
        *(f"{CAPTAIN_STEP_CALLBACK_PREFIX}P{index:03d}" for index in range(1, 26)),
    ]
    assert negative.buttons == first.buttons
    assert oversized.buttons == second.buttons
    assert all(len(button.callback_data.encode("utf-8")) <= 64 for button in first.buttons + second.buttons)


@pytest.mark.parametrize("goal_status", [None, "closed"])
def test_captain_step_view_requires_active_goal(goal_status: str | None) -> None:
    goals = [] if goal_status is None else [
        {"goal_id": "OLD", "participant_id": "P001", "goal_status": goal_status}
    ]
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain"), _participant("P001", 1001)],
        goals=goals,
        planned_steps=[{"step_id": "OLD1", "participant_id": "P001", "goal_id": "OLD", "step_number": 1, "step_title": "Старый секретный шаг", "step_status": "open"}],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_STEPS_MISSING_TEXT
    assert "Старый секретный шаг" not in response.text


def test_captain_step_view_excludes_duplicate_blank_and_out_of_range_steps() -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain"), _participant("P001", 1001)],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=[
            {"step_id": "S1", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Верный шаг", "step_status": "open"},
            {"step_id": "S2A", "participant_id": "P001", "goal_id": "G001", "step_number": 2, "step_title": "Дубль A", "step_status": "open"},
            {"step_id": "S2B", "participant_id": "P001", "goal_id": "G001", "step_number": 2, "step_title": "Дубль B", "step_status": "closed"},
            {"step_id": "S3", "participant_id": "P001", "goal_id": "G001", "step_number": 3, "step_title": "", "step_status": "open"},
            {"step_id": "S0", "participant_id": "P001", "goal_id": "G001", "step_number": 0, "step_title": "Нулевой", "step_status": "open"},
            {"step_id": "S9", "participant_id": "P001", "goal_id": "G001", "step_number": 9, "step_title": "Девятый", "step_status": "open"},
        ],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == "Шаги участника: Участник\n\n1. ⬜ Верный шаг"
    assert all(value not in response.text for value in ("Дубль", "Нулевой", "Девятый"))


@pytest.mark.parametrize(
    "participant_changes",
    [
        {"status": "dropped"},
        {"status": "inactive"},
        {"consent_given": False},
        {"role": "tracker"},
        {"flow_id": "FLOW_2"},
    ],
)
def test_forged_steps_callback_rejects_ineligible_same_team_participant(
    participant_changes: dict[str, object],
) -> None:
    target = _participant("P001", 1001, full_name="Закрытый участник")
    target.update(participant_changes)
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain"), target],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=[{"step_id": "S001", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Секретный шаг", "step_status": "open"}],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT
    assert "Секретный шаг" not in response.text


@pytest.mark.parametrize("participant_id", ["bad id", "Я" * 60])
def test_forged_steps_callback_rejects_invalid_participant_id(participant_id: str) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain")],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id=participant_id,
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT


def test_long_captain_steps_are_truncated_and_delivered_in_complete_sections() -> None:
    long_title = "Я" * 1200
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain"), _participant("P001", 1001)],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=[
            {"step_id": f"S{number}", "participant_id": "P001", "goal_id": "G001", "step_number": number, "step_title": long_title, "step_status": "open"}
            for number in range(1, 9)
        ],
    )

    response = service.show_participant_steps(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert len(response.text) > 4096
    assert len(main_bot.sent_messages) > 1
    assert all(len(message.text) <= 3900 for message in main_bot.sent_messages)
    delivered_sections: list[str] = []
    for index, message in enumerate(main_bot.sent_messages):
        sections = message.text.split("\n\n")
        if index:
            assert sections.pop(0) == "Шаги участника — продолжение"
        delivered_sections.extend(sections)
    assert delivered_sections == response.text.split("\n\n")
    assert response.text.count("...") == 8


def test_captain_cannot_view_goal_of_participant_from_another_team() -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан команды"),
            _participant("P999", 9999, team_id="T002", full_name="Чужой участник"),
        ],
        goals=[{
            "goal_id": "G999",
            "participant_id": "P999",
            "goal_title": "Чужая секретная цель",
            "goal_status": "active",
        }],
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P999",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT
    assert "Чужая секретная цель" not in response.text
    assert main_bot.sent_messages[-1].text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT


@pytest.mark.parametrize("goal_status", [None, "closed"])
def test_captain_sees_missing_text_when_participant_has_no_active_goal(
    goal_status: str | None,
) -> None:
    goals = [] if goal_status is None else [{
        "goal_id": "G001",
        "participant_id": "P001",
        "goal_title": "Закрытая цель",
        "goal_status": goal_status,
    }]
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=goals,
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_GOAL_MISSING_TEXT
    assert main_bot.sent_messages[-1].text == CAPTAIN_GOAL_MISSING_TEXT


def test_captain_goal_view_uses_safe_fallbacks_for_partial_active_goal() -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == (
        "Цель участника: Участник\n\n"
        "Цель: не указано\n\n"
        "Описание: не указано\n\n"
        "Ценность: не указана\n\n"
        "Условие разрешения: не указано\n\n"
        "Показатель выполнения: не указан"
    )
    assert "None" not in response.text


@pytest.mark.parametrize(
    "participant_changes",
    [
        {"status": "dropped"},
        {"status": "inactive"},
        {"consent_given": False},
        {"role": "tracker"},
        {"flow_id": "FLOW_2"},
    ],
)
def test_forged_goal_callback_rejects_ineligible_same_team_participant(
    participant_changes: dict[str, object],
) -> None:
    target = _participant("P001", 1001, full_name="Закрытый участник")
    target.update(participant_changes)
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain"), target],
        goals=[{
            "goal_id": "G001",
            "participant_id": "P001",
            "goal_title": "Секретная цель",
            "goal_status": "active",
        }],
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT
    assert "Секретная цель" not in response.text


def test_long_goal_is_truncated_and_delivered_in_complete_ordered_sections() -> None:
    long_value = "Я" * 1200
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[{
            "goal_id": "G001",
            "participant_id": "P001",
            "goal_title": long_value,
            "goal_description": long_value,
            "goal_value_amount": long_value,
            "goal_value_currency": "RUB",
            "permission_condition": long_value,
            "permission_metric_amount": long_value,
            "permission_metric_unit": "единиц",
            "goal_status": "active",
        }],
    )

    response = service.show_participant_goal(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        participant_id="P001",
        now=datetime.fromisoformat(NOW),
    )

    assert len(main_bot.sent_messages) > 1
    assert all(len(message.text) <= 3900 for message in main_bot.sent_messages)
    delivered_sections: list[str] = []
    for index, message in enumerate(main_bot.sent_messages):
        sections = message.text.split("\n\n")
        if index:
            assert sections.pop(0) == "Цель участника — продолжение"
        delivered_sections.extend(sections)
    assert delivered_sections == response.text.split("\n\n")
    assert response.text.count("...") == 5


def test_team_goal_list_is_paginated_and_skips_oversized_participant_id() -> None:
    participants = [_participant("C001", 2001, role="captain", full_name="Капитан")]
    participants.extend(
        _participant(f"P{index:03d}", 3000 + index, full_name=f"Участник {index:02d}")
        for index in range(1, 26)
    )
    participants.append(_participant("Я" * 60, 9999, full_name="Некорректный ID"))
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=participants,
    )

    first = service.show_team_goals(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
        page_index=0,
    )
    second = service.show_team_goals(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
        page_index=1,
    )
    negative = service.show_team_goals(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
        page_index=-5,
    )
    oversized = service.show_team_goals(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
        page_index=999,
    )

    assert len(first.buttons) == 21
    assert first.buttons[-1] == TelegramInlineButton(text="Далее →", callback_data="captain:goals_page:1")
    assert second.buttons[0] == TelegramInlineButton(text="← Назад", callback_data="captain:goals_page:0")
    assert all(button.text != "Далее →" for button in second.buttons)
    first_participants = [button for button in first.buttons if button.text != "Далее →"]
    second_participants = [button for button in second.buttons if button.text != "← Назад"]
    assert len(first_participants) == 20
    assert len(second_participants) == 6
    assert [button.callback_data for button in first_participants + second_participants] == [
        f"{CAPTAIN_GOAL_CALLBACK_PREFIX}C001",
        *(f"{CAPTAIN_GOAL_CALLBACK_PREFIX}P{index:03d}" for index in range(1, 26)),
    ]
    assert negative.buttons == first.buttons
    assert oversized.buttons == second.buttons
    assert all(len(button.callback_data.encode("utf-8")) <= 64 for button in first.buttons + second.buttons)
    assert all(button.text != "Некорректный ID" for button in first.buttons + second.buttons)


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


def test_non_captain_cannot_view_team_progress() -> None:
    service, _gateway, main_bot, error_bot, _notification_bot = _build_service(
        participants=[
            _participant("P001", 1001, role="participant", full_name="Анна Участник"),
            _participant("P002", 1002, role="participant", full_name="Борис Участник"),
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=1001, chat_id="1001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_ONLY_TEXT
    assert "Анна Участник" not in response.text
    assert "Борис Участник" not in response.text
    assert main_bot.sent_messages[-1].text == CAPTAIN_ONLY_TEXT
    assert error_bot.sent_messages == []


def test_inactive_captain_cannot_view_team_progress() -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", status="inactive", full_name="Бывший капитан"),
            _participant("P001", 1001, full_name="Участник команды"),
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_ONLY_TEXT
    assert "Участник команды" not in response.text
    assert main_bot.sent_messages[-1].text == CAPTAIN_ONLY_TEXT


def test_captain_team_progress_requires_authoritative_active_team_assignment() -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Старый капитан"),
            _participant("P001", 1001, full_name="Участник команды"),
        ],
        teams=[
            {
                "flow_id": "FLOW_1",
                "team_id": "T001",
                "team_name": "Команда",
                "captain_id": "C999",
                "is_active": True,
            }
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_ONLY_TEXT
    assert "Участник команды" not in response.text
    assert main_bot.sent_messages[-1].text == CAPTAIN_ONLY_TEXT


def test_captain_team_progress_is_not_disclosed_in_group_chat() -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Участник команды"),
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="-100123456"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text == CAPTAIN_PRIVATE_CHAT_ONLY_TEXT
    assert "Участник команды" not in response.text
    assert main_bot.sent_messages[-1].chat_id == "-100123456"


def test_team_progress_splits_large_team_at_participant_boundaries() -> None:
    participants = [_participant("C001", 2001, role="captain", full_name="Капитан")]
    participants.extend(
        _participant(f"P{index:03d}", 3000 + index, full_name=f"Участник {index:02d} " + "Я" * 70)
        for index in range(1, 41)
    )
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_service(
        participants=participants,
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert len(response.text) > 4096
    assert len(main_bot.sent_messages) > 1
    assert all(len(message.text) <= 3900 for message in main_bot.sent_messages)
    delivered_sections: list[str] = []
    for index, message in enumerate(main_bot.sent_messages):
        sections = message.text.split("\n\n")
        expected_header = (
            "Прогресс команды на текущий момент"
            if index == 0
            else "Прогресс команды — продолжение"
        )
        assert sections[0] == expected_header
        assert all(len(section.splitlines()) == 6 for section in sections[1:])
        delivered_sections.extend(sections[1:])

    assert delivered_sections == response.text.split("\n\n")[1:]
    delivered_text = "\n\n".join(delivered_sections)
    for index in range(1, 41):
        assert delivered_text.count(f"Участник {index:02d} ") == 1


def test_team_progress_ignores_wrong_week_inactive_and_invalid_focus() -> None:
    week_number = current_challenge_week_number(datetime.fromisoformat(NOW))
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        planned_steps=[{
            "step_id": "S001",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_number": 1,
            "step_title": "Верный шаг",
            "step_status": "open",
        }],
        weekly_focus=[
            {"participant_id": "P001", "step_id": "S001", "week_number": week_number - 1, "focus_status": "active"},
            {"participant_id": "P001", "step_id": "S001", "week_number": week_number, "focus_status": "inactive"},
            {"participant_id": "C001", "step_id": "FOREIGN", "week_number": week_number, "focus_status": "active"},
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    assert response.text.count("Фокус недели: не выбран") == 2


def test_team_progress_shows_focus_as_not_open_before_working_weeks() -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[_participant("C001", 2001, role="captain", full_name="Капитан")],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat("2026-05-20T10:00:00+05:00"),
    )

    assert "Фокус недели: выбор ещё не открыт" in response.text


def test_team_progress_counts_only_unique_valid_steps_of_active_goal() -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            _participant("P001", 1001, full_name="Участник"),
        ],
        goals=[
            {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
            {"goal_id": "OLD", "participant_id": "P001", "goal_status": "closed"},
        ],
        planned_steps=[
            {"step_id": "S1", "participant_id": "P001", "goal_id": "G001", "step_number": 1, "step_title": "Один", "step_status": "closed"},
            {"step_id": "S2A", "participant_id": "P001", "goal_id": "G001", "step_number": 2, "step_title": "Дубль A", "step_status": "closed"},
            {"step_id": "S2B", "participant_id": "P001", "goal_id": "G001", "step_number": 2, "step_title": "Дубль B", "step_status": "open"},
            {"step_id": "S3", "participant_id": "P001", "goal_id": "G001", "step_number": 3, "step_title": "", "step_status": "closed"},
            {"step_id": "S0", "participant_id": "P001", "goal_id": "G001", "step_number": 0, "step_title": "Ноль", "step_status": "closed"},
            {"step_id": "S9", "participant_id": "P001", "goal_id": "G001", "step_number": 9, "step_title": "Девять", "step_status": "closed"},
            {"step_id": "OLD1", "participant_id": "P001", "goal_id": "OLD", "step_number": 4, "step_title": "Старая цель", "step_status": "closed"},
        ],
    )

    response = service.show_team_progress(
        TelegramUserContext(telegram_id=2001, chat_id="2001"),
        now=datetime.fromisoformat(NOW),
    )

    participant_section = response.text.split("Участник", 1)[1]
    assert "Шаги: 🟦 1 из 8" in participant_section
    assert "Выполнено: 1 из 8 — 12%" in participant_section
    assert "🟩⬜⬜⬜⬜⬜⬜⬜" in participant_section


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
    assert response.buttons == (CONSENT_ACCEPT_BUTTON, CONSENT_DECLINE_BUTTON)
    assert "Анна Своя" not in response.text
    assert main_bot.sent_messages[-1].text == CONSENT_TEXT
    assert error_bot.sent_messages == []


def _build_service(
    *,
    participants: list[dict[str, object]],
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_focus: list[dict[str, object]] | None = None,
    teams: list[dict[str, object]] | None = None,
) -> tuple[CaptainService, FakeSheetsGateway, FakeBotClient, FakeBotClient, FakeBotClient]:
    gateway = FakeSheetsGateway(
        participants=participants,
        goals=goals or [],
        planned_steps=planned_steps or [],
        weekly_focus=weekly_focus or [],
        teams=teams
        if teams is not None
        else [{
            "flow_id": "FLOW_1",
            "team_id": "T001",
            "team_name": "Команда",
            "captain_id": "C001",
            "is_active": True,
        }],
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
    status: str = "active",
    full_name: str = "Участник",
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": team_id,
        "consent_given": consent_given,
        "status": status,
        "flow_id": "FLOW_1",
        "full_name": full_name,
    }
