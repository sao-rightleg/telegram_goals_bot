from pathlib import Path

import pytest

from app.bot.menus import MenuAction
from app.services.participant_models import TelegramUserContext
from tests.test_participant_views import (
    NOW,
    SETUP_NOW,
    _build_service,
    _goal,
    _participant,
    _step,
)


@pytest.mark.parametrize("occurred_at", [NOW, SETUP_NOW])
def test_steps_view_shows_own_flow_price_and_preserves_plan(
    tmp_path: Path, occurred_at: str
) -> None:
    participant = _participant("P001", 1001)
    service, gateway, main_bot, *_ = _build_service(
        tmp_path,
        participants=[participant, _participant("P002", 1002)],
        goals=[_goal("G001", "P001", "Моя цель")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Первый шаг", "open")],
    )
    own = {
        "flow_id": participant["flow_id"],
        "participant_id": "P001",
        "word_price_rub": 5000,
        "created_at": NOW,
        "updated_at": NOW,
    }
    gateway.save_word_price(own)
    gateway.save_word_price({**own, "flow_id": "OTHER_FLOW", "word_price_rub": 9000})
    gateway.save_word_price({**own, "participant_id": "P002", "word_price_rub": 8000})
    before = gateway.list_planned_steps("P001", "G001")

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_STEPS,
        occurred_at=occurred_at,
    )

    assert "Цена слова: 5 000 ₽" in response.text
    assert "9 000" not in response.text and "8 000" not in response.text
    assert "Прогресс:" in response.text and "⬜ Шаг 1. Первый шаг" in response.text
    assert main_bot.sent_messages[-1].text == response.text
    assert gateway.list_planned_steps("P001", "G001") == before
    assert gateway.find_word_price(str(participant["flow_id"]), "P001") == own


def test_steps_view_shows_missing_price_without_starting_interview(
    tmp_path: Path,
) -> None:
    service, gateway, _bot, *_ = _build_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001", "Моя цель")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Первый шаг", "open")],
    )
    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_STEPS,
        occurred_at=NOW,
    )
    assert "Цена слова: не указана" in response.text
    assert "Первый шаг" in response.text
    assert service.dialog_states.get(1001).flow == "view_steps"
    assert gateway._word_prices == []


def test_legacy_participant_without_flow_can_view_steps_without_foreign_price(
    tmp_path: Path,
) -> None:
    participant = _participant("P001", 1001)
    participant.pop("flow_id")
    service, gateway, _bot, *_ = _build_service(
        tmp_path,
        participants=[participant],
        goals=[_goal("G001", "P001", "Моя цель")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Первый шаг", "open")],
    )
    gateway.save_word_price(
        {
            "flow_id": "OTHER_FLOW",
            "participant_id": "P001",
            "word_price_rub": 9000,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="chat-1001"),
        MenuAction.VIEW_STEPS,
        occurred_at=NOW,
    )
    assert "Первый шаг" in response.text
    assert "Цена слова: не указана" in response.text
    assert "9 000" not in response.text
