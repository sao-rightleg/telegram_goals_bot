from pathlib import Path

import pytest

from app.bot.messages import TELEGRAM_HTML_PARSE_MODE
from app.services.participant_models import TelegramUserContext
from tests.test_participant_start_flow import (
    REGISTRATION_NOW,
    _active_flow,
    _build_service,
)


@pytest.mark.parametrize("role", ["participant", "captain"])
@pytest.mark.parametrize("late", [False, True])
def test_rules_follow_registration_success_before_next_prompt(
    tmp_path: Path, role: str, late: bool
) -> None:
    now = "2026-09-21T10:00:00+05:00" if late else REGISTRATION_NOW
    flow = {**_active_flow(), "registration_closes_at": "2026-09-26T00:00:00+05:00"}
    if late:
        flow["goal_setup_end_date"] = "2026-09-13"
    captain = {
        "flow_id": "FLOW_2",
        "participant_id": "C001",
        "telegram_id": 1001,
        "full_name": "Анна Иванова",
        "role": "captain",
        "team_id": "T001",
        "status": "active",
        "consent_given": True,
    }
    team = {
        "flow_id": "FLOW_2",
        "team_id": "T001",
        "team_name": "Команда 1",
        "captain_id": "C001",
        "is_active": True,
    }
    if role == "captain":
        team["captain_telegram_id"] = 404
    service, gateway, bot, *_ = _build_service(
        tmp_path,
        participants=[] if role == "captain" else [captain],
        teams=[team],
        challenge_flows=[flow],
    )
    user = TelegramUserContext(telegram_id=404, chat_id="404")
    service.handle_start(user, occurred_at=now)
    service.accept_consent(user, consent_given_at=now)
    service.handle_registration_text(user, "Пётр", occurred_at=now)
    service.handle_registration_text(user, "Петров", occurred_at=now)
    if role == "participant":
        service.select_registration_captain(user, captain_id="C001", occurred_at=now)

    service.confirm_registration(user, occurred_at=now)

    success_index = next(
        i
        for i, message in enumerate(bot.sent_messages)
        if "успешно зарегистрирован" in message.text
    )
    rules = bot.sent_messages[success_index + 1]
    assert rules.text.startswith("ПРАВИЛА ПРОЕКТА (читать внимательно):")
    assert "<u>Цель и шаги</u>" in rules.text
    assert "<u>Цена слова</u>" in rules.text
    assert "Реалистичность:" in rules.text and "Последствия:" in rules.text
    assert rules.text.endswith("исключается из проекта. Беспощадно.")
    assert rules.parse_mode == TELEGRAM_HTML_PARSE_MODE
    assert rules.chat_id == user.chat_id
    assert len(rules.text) < 4096
    assert gateway.find_participant_in_flow("FLOW_2", 404)["role"] == role
    if late:
        assert "Кратко напиши цель" in bot.sent_messages[success_index + 2].text

    service.confirm_registration(user, occurred_at=now)
    service.handle_start(user, occurred_at=now)
    assert (
        sum(message.text.startswith("ПРАВИЛА ПРОЕКТА") for message in bot.sent_messages)
        == 1
    )
