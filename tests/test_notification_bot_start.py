from __future__ import annotations

from datetime import datetime
from threading import Event
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.notification_dispatch import NotificationBotUpdateDispatcher
from app.runtime import NotificationBotPollingRunner
import app.runtime as runtime_module
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notification_bot import (
    NOTIFICATION_BOT_CONNECTED_TEXT,
    NOTIFICATION_BOT_FORBIDDEN_TEXT,
    NotificationBotStartService,
)
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import FakeSheetsGateway


NOW = datetime(2026, 9, 28, 14, 30, tzinfo=ZoneInfo(TIMEZONE_NAME))


def _service(*, assignments: list[dict[str, object]]) -> tuple[
    NotificationBotStartService, FakeSheetsGateway, FakeBotClient
]:
    gateway = FakeSheetsGateway(team_captains=assignments)
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    service = NotificationBotStartService(
        sheets=gateway,
        notification_bot=bot,
        flow_id="FLOW_1",
    )
    return service, gateway, bot


def test_notification_start_marks_all_active_assignments_for_captain() -> None:
    service, gateway, bot = _service(assignments=[
        {
            "flow_id": "FLOW_1", "team_id": "T001", "captain_id": "C001",
            "captain_telegram_id": 1001, "is_active": True,
        },
        {
            "flow_id": "FLOW_1", "team_id": "T002", "captain_id": "C001",
            "captain_telegram_id": 1001, "is_active": True,
        },
        {
            "flow_id": "FLOW_2", "team_id": "T003", "captain_id": "C001",
            "captain_telegram_id": 1001, "is_active": True,
        },
    ])

    response = service.handle_start(
        telegram_id=1001,
        chat_id="1001",
        occurred_at=NOW.isoformat(),
    )

    assert response.text == NOTIFICATION_BOT_CONNECTED_TEXT
    rows = gateway.list_team_captains()
    assert [row.get("notification_bot_status") for row in rows] == [
        "active", "active", None,
    ]
    assert [row.get("notification_bot_chat_id") for row in rows] == ["1001", "1001", None]
    assert [row.get("notification_bot_started_at") for row in rows] == [
        NOW.isoformat(), NOW.isoformat(), None,
    ]
    assert [message.text for message in bot.sent_messages] == [NOTIFICATION_BOT_CONNECTED_TEXT]

    service.handle_start(
        telegram_id=1001,
        chat_id="1001",
        occurred_at="2026-09-29T14:30:00+05:00",
    )
    rows = gateway.list_team_captains()
    assert rows[0]["notification_bot_started_at"] == NOW.isoformat()
    assert rows[1]["notification_bot_started_at"] == NOW.isoformat()


def test_notification_start_rejects_unknown_inactive_and_group_chat() -> None:
    for telegram_id, chat_id in ((9999, "9999"), (1002, "1002"), (1001, "-100500")):
        service, gateway, bot = _service(assignments=[
            {
                "flow_id": "FLOW_1", "team_id": "T001", "captain_id": "C001",
                "captain_telegram_id": 1001, "is_active": True,
            },
            {
                "flow_id": "FLOW_1", "team_id": "T002", "captain_id": "C002",
                "captain_telegram_id": 1002, "is_active": False,
            },
        ])

        response = service.handle_start(
            telegram_id=telegram_id,
            chat_id=chat_id,
            occurred_at=NOW.isoformat(),
        )

        assert response.text == NOTIFICATION_BOT_FORBIDDEN_TEXT
        assert all(not row.get("notification_bot_started_at") for row in gateway.list_team_captains())
        assert [message.text for message in bot.sent_messages] == [NOTIFICATION_BOT_FORBIDDEN_TEXT]


def test_notification_start_materializes_legacy_primary_assignment() -> None:
    gateway = FakeSheetsGateway(
        participants=[{"participant_id": "C001", "full_name": "Captain One"}],
        teams=[{
            "flow_id": "FLOW_1", "team_id": "T001", "captain_id": "C001",
            "captain_telegram_id": 1001, "is_active": True,
        }],
    )
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    service = NotificationBotStartService(
        sheets=gateway,
        notification_bot=bot,
        flow_id="FLOW_1",
    )

    service.handle_start(
        telegram_id=1001,
        chat_id="1001",
        occurred_at=NOW.isoformat(),
    )

    assert gateway.list_team_captains() == [{
        "flow_id": "FLOW_1",
        "team_id": "T001",
        "captain_id": "C001",
        "captain_telegram_id": 1001,
        "is_primary": True,
        "is_active": True,
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
        "captain_full_name": "Captain One",
        "notification_bot_chat_id": "1001",
        "notification_bot_started_at": NOW.isoformat(),
        "notification_bot_status": "active",
    }]


def test_notification_dispatcher_accepts_only_start_command() -> None:
    service, gateway, bot = _service(assignments=[{
        "flow_id": "FLOW_1", "team_id": "T001", "captain_id": "C001",
        "captain_telegram_id": 1001, "is_active": True,
    }])
    dispatcher = NotificationBotUpdateDispatcher(service=service, now_provider=lambda: NOW)

    dispatcher.dispatch_update({
        "update_id": 1,
        "message": {
            "message_id": 10, "from": {"id": 1001}, "chat": {"id": 1001},
            "text": "/start",
        },
    })
    dispatcher.dispatch_update({
        "update_id": 2,
        "message": {
            "message_id": 11, "from": {"id": 1001}, "chat": {"id": 1001},
            "text": "произвольный текст",
        },
    })

    assert gateway.list_team_captains()[0]["notification_bot_status"] == "active"
    assert [message.text for message in bot.sent_messages] == [NOTIFICATION_BOT_CONNECTED_TEXT]


def test_notification_polling_advances_offset_and_dispatches() -> None:
    stop_event = Event()
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    updates = [{
        "update_id": 41,
        "message": {
            "message_id": 5, "from": {"id": 1001}, "chat": {"id": 1001},
            "text": "/start",
        },
    }]
    offsets: list[int | None] = []

    def get_updates(*, offset, timeout_seconds, limit):
        del timeout_seconds, limit
        offsets.append(offset)
        if len(offsets) == 1:
            return updates
        stop_event.set()
        return []

    bot.get_updates = get_updates
    dispatched: list[dict[str, object]] = []
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=error_bot,
        notification_bot=bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    components = SimpleNamespace(
        notification_bot=bot,
        notification_bot_dispatcher=SimpleNamespace(
            dispatch_update=lambda update: dispatched.append(update)
        ),
        notification_router=router,
    )

    NotificationBotPollingRunner(
        poll_timeout_seconds=1,
        poll_limit=10,
        stop_event=stop_event,
    ).run(components)

    assert offsets == [None, 42]
    assert dispatched == updates
    assert error_bot.sent_messages == []


def test_notification_polling_retries_failed_update_without_advancing_offset(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "RUNTIME_RETRY_MAX_SECONDS", 0)
    stop_event = Event()
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    update = {
        "update_id": 41,
        "message": {
            "message_id": 5, "from": {"id": 1001}, "chat": {"id": 1001},
            "text": "/start",
        },
    }
    offsets: list[int | None] = []

    def get_updates(*, offset, timeout_seconds, limit):
        del timeout_seconds, limit
        offsets.append(offset)
        if offset == 42:
            stop_event.set()
            return []
        return [update]

    bot.get_updates = get_updates
    attempts = 0

    def dispatch(_update):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("private provider detail")

    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=error_bot,
        notification_bot=bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    components = SimpleNamespace(
        notification_bot=bot,
        notification_bot_dispatcher=SimpleNamespace(dispatch_update=dispatch),
        notification_router=router,
    )

    NotificationBotPollingRunner(1, 10, stop_event).run(components)

    assert offsets == [None, None, 42]
    assert attempts == 2
    assert len(error_bot.sent_messages) == 1
    assert "notification_bot_update_dispatch_failed" in error_bot.sent_messages[0].text
    assert "private provider detail" not in error_bot.sent_messages[0].text


def test_notification_polling_reports_malformed_update_failure_once(monkeypatch) -> None:
    monkeypatch.setattr(runtime_module, "RUNTIME_RETRY_MAX_SECONDS", 0)
    stop_event = Event()
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    calls = 0

    def get_updates(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            stop_event.set()
            return []
        return [{"message": {"text": "/start"}}]

    bot.get_updates = get_updates
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN), error_bot=error_bot,
        notification_bot=bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    components = SimpleNamespace(
        notification_bot=bot,
        notification_bot_dispatcher=SimpleNamespace(
            dispatch_update=lambda _update: (_ for _ in ()).throw(ValueError("private"))
        ),
        notification_router=router,
    )

    NotificationBotPollingRunner(1, 10, stop_event).run(components)

    assert len(error_bot.sent_messages) == 2
    assert "notification_bot_update_dispatch_failed" in error_bot.sent_messages[0].text
    assert "notification_bot_update_abandoned" in error_bot.sent_messages[1].text
    assert all("private" not in message.text for message in error_bot.sent_messages)


def test_notification_polling_alerts_after_three_get_updates_failures_and_recovers(
    monkeypatch,
) -> None:
    monkeypatch.setattr(runtime_module, "RUNTIME_RETRY_MAX_SECONDS", 0)
    stop_event = Event()
    bot = FakeBotClient(BotPurpose.NOTIFICATION)
    calls = 0

    def get_updates(**_kwargs):
        nonlocal calls
        calls += 1
        if calls <= 3:
            raise RuntimeError("private provider detail")
        stop_event.set()
        return []

    bot.get_updates = get_updates
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN), error_bot=error_bot,
        notification_bot=bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    components = SimpleNamespace(
        notification_bot=bot,
        notification_bot_dispatcher=SimpleNamespace(dispatch_update=lambda _update: None),
        notification_router=router,
    )

    NotificationBotPollingRunner(1, 10, stop_event).run(components)

    assert [message.text for message in error_bot.sent_messages] == [
        "notification_bot_get_updates_failed error_type=RuntimeError "
        "consecutive_failures=3",
        "notification_bot_get_updates_recovered",
    ]
