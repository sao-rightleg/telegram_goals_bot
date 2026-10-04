from pathlib import Path

import pytest

from app.bot.menus import MenuAction, build_role_menu
from app.services.participant_models import TelegramUserContext
from tests.test_participant_views import NOW, _build_service, _participant


def setup(tmp_path, **changes):
    participant = {**_participant("P001", 1001), **changes}
    service, gateway, bot, *_ = _build_service(tmp_path, participants=[participant])
    return service, gateway, bot, TelegramUserContext(1001, "1001")


def test_menu_and_save_append_replace_cancel(tmp_path: Path):
    service, gateway, bot, user = setup(tmp_path)
    for role in ("participant", "captain"):
        assert "О себе" in [item.label for item in build_role_menu(role)]
    response = service.handle_menu_action(user, MenuAction.VIEW_ABOUT, occurred_at=NOW)
    assert "чем" in response.text
    service.handle_about_action(user, "replace", occurred_at=NOW)
    service.handle_about_text(user, "Разработчик. Помогаю с Python.", occurred_at=NOW)
    assert (
        gateway.get_participant("P001")["about_me"] == "Разработчик. Помогаю с Python."
    )
    service.handle_about_action(user, "append", occurred_at=NOW)
    service.handle_about_text(user, "Раньше преподавал.", occurred_at=NOW)
    expected = "Разработчик. Помогаю с Python.\n\nРаньше преподавал."
    assert gateway.get_participant("P001")["about_me"] == expected
    service.handle_about_text(user, "Раньше преподавал.", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == expected
    service.handle_about_action(user, "replace", occurred_at=NOW)
    service.handle_about_action(user, "cancel", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == expected
    service.handle_about_action(user, "replace", occurred_at=NOW)
    service.handle_about_text(user, "Новое описание", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Новое описание"
    assert all(message.parse_mode is None for message in bot.sent_messages)


@pytest.mark.parametrize(
    "changes,chat",
    [
        ({"consent_given": False}, "1001"),
        ({"status": "dropped"}, "1001"),
        ({"role": "tracker"}, "1001"),
        ({}, "-1001"),
        ({"flow_id": ""}, "1001"),
    ],
)
def test_denied_profile_access(tmp_path, changes, chat):
    service, gateway, bot, user = setup(tmp_path, about_me="Секрет", **changes)
    user = TelegramUserContext(1001, chat)
    service.handle_menu_action(user, MenuAction.VIEW_ABOUT, occurred_at=NOW)
    service.handle_about_action(user, "replace", occurred_at=NOW)
    service.handle_about_text(user, "Подмена", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Секрет"
    assert all("Секрет" not in message.text for message in bot.sent_messages)


def test_invalid_text_and_failure_preserve_edit_state(tmp_path, monkeypatch):
    service, gateway, bot, user = setup(tmp_path, about_me="Опыт")
    service.handle_about_action(user, "append", occurred_at=NOW)
    for text in ("   ", "x" * 12001):
        service.handle_about_text(user, text, occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Опыт"

    def fail(*args, **kwargs):
        raise RuntimeError("private backend details")

    monkeypatch.setattr(gateway, "update_participant_about", fail)
    response = service.handle_about_text(user, "Компетенции", occurred_at=NOW)
    assert "попробуйте" in response.text.lower()
    assert "private" not in response.text
    assert service.dialog_states.get(1001).step == "append"


def test_scope_change_blocks_pending_write(tmp_path):
    service, gateway, bot, user = setup(tmp_path, about_me="Опыт")
    service.handle_about_action(user, "append", occurred_at=NOW)
    gateway._participants[0]["flow_id"] = "OTHER_FLOW"
    service.handle_about_text(user, "Подмена", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Опыт"


def test_long_profile_is_split_and_preserved(tmp_path):
    text = "😀<текст>" * 1000
    service, gateway, bot, user = setup(tmp_path, about_me=text)
    service.handle_menu_action(user, MenuAction.VIEW_ABOUT, occurred_at=NOW)
    assert all(
        len(message.text.encode("utf-16-le")) // 2 <= 4096
        for message in bot.sent_messages
    )
    assert (
        text
        == "".join(message.text for message in bot.sent_messages)[len("О себе\n\n") :]
    )


def test_dispatcher_routes_menu_callbacks_and_text(tmp_path):
    from datetime import datetime
    from app.bot.dispatch import TelegramUpdateDispatcher

    service, gateway, bot, user = setup(tmp_path)
    dispatcher = TelegramUpdateDispatcher(
        participant_service=service,
        weekly_report_service=None,
        insight_service=None,
        captain_service=None,
        dialog_states=service.dialog_states,
        notification_router=service.notification_router,
        now_provider=lambda: datetime.fromisoformat(NOW),
    )
    for data in ("menu:view_about", "about:replace"):
        dispatcher.dispatch_update(
            {
                "update_id": 1,
                "callback_query": {
                    "id": "cb",
                    "from": {"id": 1001},
                    "data": data,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 1001, "type": "private"},
                    },
                },
            }
        )
    dispatcher.dispatch_update(
        {
            "update_id": 2,
            "message": {
                "message_id": 2,
                "from": {"id": 1001},
                "chat": {"id": 1001, "type": "private"},
                "text": "Разрабатываю приложения",
            },
        }
    )
    assert gateway.get_participant("P001")["about_me"] == "Разрабатываю приложения"


def test_edit_survives_repository_recreation(tmp_path):
    from app.storage.dialog_state import DialogStateRepository
    from dataclasses import replace

    service, gateway, bot, user = setup(tmp_path)
    service.handle_about_action(user, "replace", occurred_at=NOW)
    # Use the same configured database path; restart must preserve the editing state.
    restored = replace(
        service, dialog_states=DialogStateRepository(service.dialog_states._db_path)
    )
    restored.handle_about_text(user, "Работаю аналитиком", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Работаю аналитиком"


@pytest.mark.parametrize("failure", ["sheets", "sqlite"])
def test_append_retry_after_ambiguous_success_does_not_duplicate(
    tmp_path, monkeypatch, failure
):
    service, gateway, bot, user = setup(tmp_path, about_me="Опыт")
    service.handle_about_action(user, "append", occurred_at=NOW)
    if failure == "sheets":
        original = gateway.update_participant_about

        def fail_after_write(*args):
            original(*args)
            raise RuntimeError("response lost")

        monkeypatch.setattr(gateway, "update_participant_about", fail_after_write)
    else:
        original_upsert = service.dialog_states.upsert

        def fail_after_write(state):
            if state.step == "view":
                raise RuntimeError("sqlite temporarily unavailable")
            original_upsert(state)

        monkeypatch.setattr(service.dialog_states, "upsert", fail_after_write)
    service.handle_about_text(user, "Новый абзац", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Опыт\n\nНовый абзац"
    monkeypatch.undo()
    service.handle_about_text(user, "Новый абзац", occurred_at=NOW)
    assert gateway.get_participant("P001")["about_me"] == "Опыт\n\nНовый абзац"
    assert service.dialog_states.get(1001).step == "view"


@pytest.mark.parametrize("new_length,accepted", [(9998, True), (9999, False)])
def test_append_enforces_combined_length(tmp_path, new_length, accepted):
    old = "x" * 2000
    service, gateway, bot, user = setup(tmp_path, about_me=old)
    service.handle_about_action(user, "append", occurred_at=NOW)
    service.handle_about_text(user, "y" * new_length, occurred_at=NOW)
    saved = gateway.get_participant("P001")["about_me"]
    assert saved == old + "\n\n" + "y" * new_length if accepted else saved == old


def test_empty_profile_prompt_contains_all_topics_and_fill_button(tmp_path):
    service, gateway, bot, user = setup(tmp_path)
    response = service.handle_menu_action(user, MenuAction.VIEW_ABOUT, occurred_at=NOW)
    assert [button.text for button in response.buttons] == ["Заполнить"]
    for topic in (
        "занимаетесь сейчас",
        "занимались раньше",
        "компетенции",
        "помочь команде",
    ):
        assert topic in response.text
