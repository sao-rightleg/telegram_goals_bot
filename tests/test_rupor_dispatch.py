from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.rupor_dispatch import RuporUpdateDispatcher
from app.runtime import RuporPollingRunner
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import FlowResponse
from threading import Event


class RecordingRuporService:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def handle_start(
        self, *, telegram_id: int, chat_id: str, occurred_at: str
    ) -> FlowResponse:
        self.calls.append(("start", telegram_id, chat_id, occurred_at))
        return FlowResponse(chat_id=chat_id, text="start")

    def receive_text(
        self, *, telegram_id: int, chat_id: str, text: str, occurred_at: str
    ) -> FlowResponse:
        self.calls.append(("text", telegram_id, chat_id, text, occurred_at))
        return FlowResponse(chat_id=chat_id, text="text")

    def handle_callback(
        self, *, telegram_id: int, chat_id: str, callback_data: str, occurred_at: str
    ) -> FlowResponse:
        self.calls.append(("callback", telegram_id, chat_id, callback_data, occurred_at))
        return FlowResponse(chat_id=chat_id, text="callback")


def test_rupor_dispatcher_routes_start_text_and_callback() -> None:
    service = RecordingRuporService()
    now = datetime(2026, 9, 17, 15, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))
    dispatcher = RuporUpdateDispatcher(service=service, now_provider=lambda: now)

    dispatcher.dispatch_update({
        "update_id": 1,
        "message": {"message_id": 10, "from": {"id": 101}, "chat": {"id": 101}, "text": "/start"},
    })
    dispatcher.dispatch_update({
        "update_id": 2,
        "message": {"message_id": 11, "from": {"id": 101}, "chat": {"id": 101}, "text": "Текст"},
    })
    dispatcher.dispatch_update({
        "update_id": 3,
        "callback_query": {
            "id": "cb-1", "from": {"id": 101}, "data": "rupor:send:B1",
            "message": {"message_id": 12, "chat": {"id": 101}},
        },
    })

    assert service.calls == [
        ("start", 101, "101", now.isoformat()),
        ("text", 101, "101", "Текст", now.isoformat()),
        ("callback", 101, "101", "rupor:send:B1", now.isoformat()),
    ]


def test_rupor_polling_acknowledges_callback_and_dispatches_update() -> None:
    stop_event = Event()
    bot = FakeBotClient(BotPurpose.RUPOR)
    update = {
        "update_id": 7,
        "callback_query": {
            "id": "cb-7", "from": {"id": 101}, "data": "rupor:cancel:B1",
            "message": {"message_id": 12, "chat": {"id": 101}},
        },
    }
    requested_offsets: list[int | None] = []

    def get_updates(*, offset, timeout_seconds, limit):
        requested_offsets.append(offset)
        if requested_offsets == [None]:
            return [update]
        stop_event.set()
        return []

    bot.get_updates = get_updates
    dispatched: list[dict[str, object]] = []
    recovery_calls: list[bool] = []
    dispatcher = SimpleNamespace(
        dispatch_update=lambda item: dispatched.append(item),
        resume_incomplete=lambda: recovery_calls.append(True),
    )
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=FakeBotClient(BotPurpose.MAIN),
        error_bot=error_bot,
        notification_bot=FakeBotClient(BotPurpose.NOTIFICATION),
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    components = SimpleNamespace(
        rupor_bot=bot,
        rupor_dispatcher=dispatcher,
        notification_router=router,
    )

    RuporPollingRunner(poll_timeout_seconds=1, poll_limit=10, stop_event=stop_event).run(components)

    assert bot.answered_callback_query_ids == ["cb-7"]
    assert recovery_calls == [True]
    assert dispatched == [update]
    assert requested_offsets == [None, 8]
    assert error_bot.sent_messages == []
