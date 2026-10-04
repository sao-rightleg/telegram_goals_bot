from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from app.bot.menus import MenuAction, build_role_menu
from app.bot.messages import (
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_PRIVATE_CHAT_ONLY_TEXT,
    CONSENT_TEXT,
)
from app.services.participant_models import TelegramUserContext
from tests.test_captain_team_flow import NOW, _build_service, _participant
from tests.test_runtime_entrypoint import _callback_update, _dispatcher


USER = TelegramUserContext(telegram_id=2001, chat_id="2001")


def test_word_prices_button_is_captain_only() -> None:
    buttons = [
        item
        for item in build_role_menu("captain")
        if item.label == "Цена слова участников"
    ]
    assert len(buttons) == 1
    assert buttons[0].action == MenuAction.VIEW_TEAM_WORD_PRICES
    assert "Цена слова участников" not in [
        item.label for item in build_role_menu("participant")
    ]


def test_captain_sees_only_consented_active_own_team_prices() -> None:
    captain = _participant("C001", 2001, role="captain", full_name="Капитан команды")
    other_flow = {
        **_participant("P006", 1006, full_name="Другой поток"),
        "flow_id": "FLOW_2",
    }
    service, gateway, main_bot, *_ = _build_service(
        participants=[
            captain,
            _participant("P001", 1001, full_name="Анна Своя"),
            _participant("P002", 1002, full_name="Борис Свой"),
            _participant("P003", 1003, team_id="T002", full_name="Чужая команда"),
            _participant("P004", 1004, status="dropped", full_name="Выбывший"),
            _participant("P005", 1005, consent_given=False, full_name="Без согласия"),
            other_flow,
        ]
    )
    row = {
        "flow_id": "FLOW_1",
        "participant_id": "P001",
        "word_price_rub": 5000,
        "created_at": NOW,
        "updated_at": NOW,
    }
    gateway.save_word_price(row)
    gateway.save_word_price({**row, "flow_id": "FLOW_2", "word_price_rub": 9000})
    gateway.save_word_price({**row, "participant_id": "C001", "word_price_rub": 10000})
    before = list(gateway._word_prices)
    response = service.show_team_word_prices(USER, now=datetime.fromisoformat(NOW))
    assert response.text == (
        "Цена слова участников\n\nАнна Своя — 5 000 ₽\n\n"
        "Борис Свой — не указана\n\nКапитан команды — 10 000 ₽"
    )
    assert main_bot.sent_messages[-1].text == response.text
    assert response.buttons == ()
    assert gateway._word_prices == before


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("role", "participant", CAPTAIN_ONLY_TEXT),
        ("status", "dropped", CAPTAIN_ONLY_TEXT),
        ("consent_given", False, CONSENT_TEXT),
    ],
)
def test_unauthorized_user_cannot_view_team_prices(field, value, expected) -> None:
    captain = {**_participant("C001", 2001, role="captain"), field: value}
    service, _gateway, *_ = _build_service(participants=[captain])
    response = service.show_team_word_prices(USER, now=datetime.fromisoformat(NOW))
    assert response.text == expected


def test_team_prices_reject_group_chat() -> None:
    service, _gateway, *_ = _build_service(
        participants=[_participant("C001", 2001, role="captain")]
    )
    response = service.show_team_word_prices(
        TelegramUserContext(telegram_id=2001, chat_id="-100123"),
        now=datetime.fromisoformat(NOW),
    )
    assert response.text == CAPTAIN_PRIVATE_CHAT_ONLY_TEXT


def test_revoked_captain_cannot_view_team_prices() -> None:
    service, _gateway, *_ = _build_service(
        participants=[_participant("C001", 2001, role="captain")],
        team_captains=[
            {
                "flow_id": "FLOW_1",
                "team_id": "T001",
                "captain_id": "C001",
                "captain_telegram_id": 2001,
                "is_primary": True,
                "is_active": False,
            }
        ],
    )
    assert (
        service.show_team_word_prices(USER, now=datetime.fromisoformat(NOW)).text
        == CAPTAIN_ONLY_TEXT
    )


def test_large_team_prices_are_split_without_losing_participants() -> None:
    service, _gateway, main_bot, *_ = _build_service(
        participants=[
            _participant("C001", 2001, role="captain", full_name="Капитан"),
            *[
                _participant(
                    f"P{i:03}", 10000 + i, full_name=f"Участник {i:03} " + "А" * 80
                )
                for i in range(100)
            ],
        ]
    )
    response = service.show_team_word_prices(USER, now=datetime.fromisoformat(NOW))
    assert len(main_bot.sent_messages) > 1
    delivered = []
    for message in main_bot.sent_messages:
        assert len(message.text) <= 3900
        delivered.extend(message.text.split("\n\n")[1:])
    assert delivered == response.text.split("\n\n")[1:]


def test_button_dispatches_to_real_captain_service(tmp_path: Path) -> None:
    service, _gateway, *_ = _build_service(
        participants=[
            _participant("C001", 1001, role="captain", full_name="Капитан"),
        ],
        teams=[
            {
                "flow_id": "FLOW_1",
                "team_id": "T001",
                "captain_id": "C001",
                "is_active": True,
            }
        ],
    )
    dispatcher, _services, _error_bot = _dispatcher(tmp_path)
    dispatcher = replace(dispatcher, captain_service=service)
    payload = _callback_update(data="menu:view_team_word_prices")
    payload["callback_query"]["message"]["chat"]["id"] = "1001"
    response = dispatcher.dispatch_update(payload)
    assert "Капитан — не указана" in response.text
