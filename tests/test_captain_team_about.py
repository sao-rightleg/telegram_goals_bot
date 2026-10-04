from html import unescape
import re
from dataclasses import replace

import pytest

from app.bot.messages import (
    CAPTAIN_ONLY_TEXT,
    CAPTAIN_PRIVATE_CHAT_ONLY_TEXT,
    CONSENT_TEXT,
)
from app.services.participant_models import TelegramUserContext
from tests.test_captain_team_flow import NOW, _build_service, _participant
from tests.test_runtime_entrypoint import _callback_update, _dispatcher

USER = TelegramUserContext(2001, "2001")


def build(*members, **kwargs):
    captain = _participant("C001", 2001, role="captain", full_name="Капитан")
    return _build_service(participants=[captain, *members], **kwargs)


def test_team_names_and_expandable_profiles_are_current_and_scoped():
    own = {
        **_participant("P001", 1001, full_name="Анна <Своя>"),
        "about_me": "Опыт & навыки\nПомогу <команде>",
    }
    foreign = [
        {**_participant("P002", 1002, team_id="T002"), "about_me": "ЧУЖАЯ КОМАНДА"},
        {**_participant("P003", 1003), "flow_id": "OTHER", "about_me": "ЧУЖОЙ ПОТОК"},
        {**_participant("P004", 1004, consent_given=False), "about_me": "БЕЗ СОГЛАСИЯ"},
        {**_participant("P005", 1005, status="dropped"), "about_me": "ВЫБЫВШИЙ"},
    ]
    service, gateway, bot, *_ = build(own, *foreign)
    before = gateway.list_participants()
    response = service.show_team(USER, occurred_at=NOW)
    assert "Анна &lt;Своя&gt;" in response.text
    assert (
        "<blockquote expandable>Опыт &amp; навыки\nПомогу &lt;команде&gt;</blockquote>"
        in response.text
    )
    assert "О себе пока не заполнено" in response.text
    for row in foreign:
        assert row["about_me"] not in response.text
    assert all(message.parse_mode == "HTML" for message in bot.sent_messages)
    assert gateway.list_participants() == before
    gateway.update_participant_about("FLOW_1", "P001", "Новый опыт")
    response = service.show_team(USER, occurred_at=NOW)
    assert "Новый опыт" in response.text and "Опыт &amp;" not in response.text


@pytest.mark.parametrize(
    "text", ["😀<&>\n" * 2000, "a" * 12000], ids=["emoji-html", "max-text"]
)
def test_long_profiles_are_complete_and_messages_are_bounded(text):
    service, gateway, bot, *_ = build(
        {**_participant("P001", 1001, full_name="Анна"), "about_me": text}
    )
    service.show_team(USER, occurred_at=NOW)
    parts = []
    for message in bot.sent_messages:
        assert len(message.text.encode("utf-16-le")) // 2 <= 3900
        assert message.text.count("<blockquote expandable>") == message.text.count(
            "</blockquote>"
        )
        parts.extend(
            re.findall(r"<blockquote expandable>(.*?)</blockquote>", message.text, re.S)
        )
    assert "".join(unescape(part) for part in parts) == text
    assert len(bot.sent_messages) > 1
    assert "продолжение" in bot.sent_messages[-1].text


@pytest.mark.parametrize(
    "change,expected",
    [
        ({"role": "participant"}, CAPTAIN_ONLY_TEXT),
        ({"status": "dropped"}, CAPTAIN_ONLY_TEXT),
        ({"consent_given": False}, CONSENT_TEXT),
    ],
)
def test_profile_view_rechecks_captain_access(change, expected):
    captain = {**_participant("C001", 2001, role="captain"), **change}
    member = {**_participant("P001", 1001), "about_me": "Секрет"}
    service, gateway, bot, *_ = _build_service(participants=[captain, member])
    response = service.show_team(USER, occurred_at=NOW)
    assert response.text == expected
    assert all("Секрет" not in message.text for message in bot.sent_messages)


def test_group_chat_cannot_receive_profiles():
    service, gateway, bot, *_ = build(
        {**_participant("P001", 1001), "about_me": "Секрет"}
    )
    assert (
        service.show_team(TelegramUserContext(2001, "-100123"), occurred_at=NOW).text
        == CAPTAIN_PRIVATE_CHAT_ONLY_TEXT
    )
    assert all("Секрет" not in message.text for message in bot.sent_messages)


def test_many_members_are_split_without_losing_profiles():
    members = [
        {
            **_participant(f"P{index:03}", 1000 + index, full_name=f"Имя {index:03}"),
            "about_me": f"Описание {index:03}",
        }
        for index in range(1, 101)
    ]
    service, gateway, bot, *_ = build(*members)
    service.show_team(USER, occurred_at=NOW)
    text = "\n".join(message.text for message in bot.sent_messages)
    for member in members:
        assert text.count(member["full_name"]) == 1
        assert text.count(member["about_me"]) == 1
    assert len(bot.sent_messages) > 1
    assert all(
        len(message.text.encode("utf-16-le")) // 2 <= 3900
        for message in bot.sent_messages
    )


def test_existing_menu_callback_opens_expandable_descriptions(tmp_path):
    service, gateway, bot, *_ = build(
        {**_participant("P001", 1001), "about_me": "Помогаю с кодом"}
    )
    dispatcher, *_ = _dispatcher(tmp_path)
    dispatcher = replace(dispatcher, captain_service=service)
    payload = _callback_update(data="menu:view_team")
    payload["callback_query"]["from"]["id"] = 2001
    payload["callback_query"]["message"]["chat"]["id"] = 2001
    response = dispatcher.dispatch_update(payload)
    assert "<blockquote expandable>Помогаю с кодом</blockquote>" in response.text
    assert bot.sent_messages[-1].parse_mode == "HTML"
