from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.services.notifications import NotificationCategory, NotificationRouter, Recipient, RecipientType


def test_fake_bot_client_records_document_sends() -> None:
    bot = FakeBotClient(BotPurpose.NOTIFICATION)

    document = bot.send_document(
        chat_id="chat-1",
        file_path=Path("/tmp/team.pdf"),
        caption="Команда А",
    )

    assert document.chat_id == "chat-1"
    assert document.file_path == Path("/tmp/team.pdf")
    assert document.caption == "Команда А"
    assert bot.sent_documents == [document]


def test_notification_router_sends_report_documents_with_notification_bot() -> None:
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = _router(main_bot, error_bot, notification_bot)

    sent = router.send_document(
        category=NotificationCategory.REPORT_DELIVERY,
        file_path=Path("/tmp/team.pdf"),
        caption="PDF отчёт",
        recipients=[Recipient(RecipientType.CAPTAIN, "captain-chat")],
    )

    assert [document.chat_id for document in sent] == ["captain-chat"]
    assert notification_bot.sent_documents[0].file_path == Path("/tmp/team.pdf")


def test_report_document_delivery_does_not_use_main_or_error_bot() -> None:
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = _router(main_bot, error_bot, notification_bot)

    router.send_document(
        category=NotificationCategory.REPORT_DELIVERY,
        file_path=Path("/tmp/team.pdf"),
        caption=None,
        recipients=[Recipient(RecipientType.TRACKER, "tracker-chat")],
    )

    assert main_bot.sent_documents == []
    assert error_bot.sent_documents == []
    assert len(notification_bot.sent_documents) == 1


def test_existing_text_notification_routing_still_works() -> None:
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = _router(main_bot, error_bot, notification_bot)

    router.send(
        category=NotificationCategory.PARTICIPANT_MESSAGE,
        text="participant",
        recipients=[Recipient(RecipientType.PARTICIPANT, "participant-chat")],
    )
    router.send(
        category=NotificationCategory.TECHNICAL_ERROR,
        text="error",
        recipients=[Recipient(RecipientType.ADMIN, "ignored-chat")],
    )
    router.send(
        category=NotificationCategory.REPORT_DELIVERY,
        text="report",
        recipients=[Recipient(RecipientType.CAPTAIN, "captain-chat")],
    )

    assert [message.chat_id for message in main_bot.sent_messages] == ["participant-chat"]
    assert [message.chat_id for message in error_bot.sent_messages] == ["admin-errors"]
    assert [message.chat_id for message in notification_bot.sent_messages] == ["captain-chat"]


def _router(
    main_bot: FakeBotClient,
    error_bot: FakeBotClient,
    notification_bot: FakeBotClient,
) -> NotificationRouter:
    return NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
