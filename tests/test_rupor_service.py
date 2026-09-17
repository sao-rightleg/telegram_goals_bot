from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.rupor import RuporService
from app.sheets.gateway import FakeSheetsGateway
from app.storage.rupor import RuporRepository
from app.storage.sqlite import initialize_schema


NOW = "2026-09-17T15:00:00+05:00"


def _build_service(tmp_path: Path, *, participants=None, allowed_ids=(101, 102, 103)):
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    rupor_bot = FakeBotClient(BotPurpose.RUPOR)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    repository = RuporRepository(db_path)
    service = RuporService(
        sheets=FakeSheetsGateway(participants=participants or []),
        rupor_bot=rupor_bot,
        delivery_bot=main_bot,
        notification_router=router,
        repository=repository,
        allowed_telegram_ids=frozenset(allowed_ids),
        delivery_pause_seconds=0,
    )
    return service, rupor_bot, main_bot, error_bot, repository


def test_rupor_rejects_unknown_and_group_chat_without_exposing_audience(tmp_path: Path) -> None:
    service, rupor_bot, main_bot, _error_bot, repository = _build_service(tmp_path)

    unauthorized = service.receive_text(
        telegram_id=999, chat_id="999", text="Секретная рассылка", occurred_at=NOW
    )
    group = service.receive_text(
        telegram_id=101, chat_id="-100123", text="Сообщение", occurred_at=NOW
    )

    assert unauthorized.text == ""
    assert group.text == "Рассылку можно создавать только в личном чате с ботом."
    assert repository.get_draft(999) is None
    assert repository.get_draft(101) is None
    assert main_bot.sent_messages == []
    assert [item.text for item in rupor_bot.sent_messages] == [group.text]


def test_rupor_previews_text_and_exact_eligible_recipient_count(tmp_path: Path) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
        {"participant_id": "P2", "telegram_id": 202, "role": "participant", "status": "active", "consent_given": True},
        {"participant_id": "C1", "telegram_id": 203, "role": "captain", "status": "active", "consent_given": True},
        {"participant_id": "P3", "telegram_id": 204, "role": "participant", "status": "dropped", "consent_given": True},
        {"participant_id": "P4", "telegram_id": 205, "role": "participant", "status": "active", "consent_given": False},
        {"participant_id": "P5", "telegram_id": "", "role": "participant", "status": "active", "consent_given": True},
    ]
    service, rupor_bot, _main_bot, _error_bot, repository = _build_service(
        tmp_path, participants=participants
    )

    response = service.receive_text(
        telegram_id=101, chat_id="101", text="Встреча завтра в 19:00", occurred_at=NOW
    )

    assert response.text == (
        "Предпросмотр рассылки\n\n"
        "Получателей: 2\n\n"
        "Встреча завтра в 19:00\n\n"
        "Отправить сообщение?"
    )
    assert [button.text for button in response.buttons] == ["Отправить всем", "Отмена"]
    draft = repository.get_draft(101)
    assert draft is not None
    assert draft.message_text == "Встреча завтра в 19:00"
    assert rupor_bot.sent_messages[-1].buttons == response.buttons


def test_rupor_cancel_removes_message_text_and_never_delivers(tmp_path: Path) -> None:
    service, _rupor_bot, main_bot, _error_bot, repository = _build_service(tmp_path)
    preview = service.receive_text(
        telegram_id=101, chat_id="101", text="Не отправлять", occurred_at=NOW
    )

    response = service.handle_callback(
        telegram_id=101,
        chat_id="101",
        callback_data=preview.buttons[1].callback_data,
        occurred_at=NOW,
    )

    assert response.text == "Рассылка отменена."
    assert main_bot.sent_messages == []
    draft = repository.get_draft(101)
    assert draft is not None
    assert draft.status == "cancelled"
    assert draft.message_text is None


def test_rupor_sends_once_to_each_eligible_participant_and_returns_summary(tmp_path: Path) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
        {"participant_id": "P2", "telegram_id": 202, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, rupor_bot, main_bot, error_bot, repository = _build_service(
        tmp_path, participants=participants
    )
    preview = service.receive_text(
        telegram_id=102, chat_id="102", text="Общее сообщение", occurred_at=NOW
    )
    callback = preview.buttons[0].callback_data

    started = service.handle_callback(
        telegram_id=102, chat_id="102", callback_data=callback, occurred_at=NOW
    )
    repeated = service.handle_callback(
        telegram_id=102, chat_id="102", callback_data=callback, occurred_at=NOW
    )

    assert started.text == "Рассылка запущена. Получателей: 2."
    assert repeated.text == "Эта рассылка уже обработана."
    assert [(item.chat_id, item.text) for item in main_bot.sent_messages] == [
        ("201", "Общее сообщение"),
        ("202", "Общее сообщение"),
    ]
    assert rupor_bot.sent_messages[-2].text == "Рассылка завершена. Доставлено: 2. Ошибок: 0."
    assert error_bot.sent_messages == []
    draft = repository.get_draft(102)
    assert draft is not None
    assert draft.status == "sent"
    assert draft.message_text is None


def test_rupor_ambiguous_delivery_failure_does_not_stop_others_or_auto_retry(
    tmp_path: Path,
) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
        {"participant_id": "P2", "telegram_id": 202, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, rupor_bot, main_bot, error_bot, repository = _build_service(
        tmp_path, participants=participants
    )
    original_send = main_bot.send_message

    def fail_one(*, chat_id: str, text: str, **kwargs):
        if chat_id == "201":
            raise RuntimeError("private provider detail")
        return original_send(chat_id=chat_id, text=text, **kwargs)

    main_bot.send_message = fail_one
    preview = service.receive_text(
        telegram_id=103, chat_id="103", text="Проверка", occurred_at=NOW
    )
    service.handle_callback(
        telegram_id=103,
        chat_id="103",
        callback_data=preview.buttons[0].callback_data,
        occurred_at=NOW,
    )

    assert [(item.chat_id, item.text) for item in main_bot.sent_messages] == [("202", "Проверка")]
    assert rupor_bot.sent_messages[-1].text == (
        "Рассылка завершена. Доставлено: 1. Ошибок: 0. "
        "Неопределённый статус: 1. Автоповтор отключён, чтобы не отправить сообщение дважды."
    )
    assert len(error_bot.sent_messages) == 1
    assert "private provider detail" not in error_bot.sent_messages[0].text
    assert repository.delivery_status(repository.get_draft(103).broadcast_id, "P1") == "unknown"
    assert repository.delivery_status(repository.get_draft(103).broadcast_id, "P2") == "sent"

    main_bot.send_message = original_send
    service.handle_start(telegram_id=103, chat_id="103", occurred_at="2026-09-17T15:01:00+05:00")

    assert [(item.chat_id, item.text) for item in main_bot.sent_messages] == [
        ("202", "Проверка"),
    ]
    assert repository.delivery_status(repository.get_draft(103).broadcast_id, "P1") == "unknown"
    assert repository.get_draft(103).status == "sending"


def test_rupor_resumes_persisted_partial_broadcast_after_process_restart(tmp_path: Path) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
        {"participant_id": "P2", "telegram_id": 202, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, _rupor_bot, main_bot, _error_bot, repository = _build_service(
        tmp_path, participants=participants
    )
    preview = service.receive_text(
        telegram_id=101, chat_id="101", text="После рестарта", occurred_at=NOW
    )
    broadcast_id = repository.get_draft(101).broadcast_id
    for participant_id in ("P1", "P2"):
        repository.ensure_delivery(broadcast_id, participant_id, updated_at=NOW)
    assert repository.claim_broadcast(101, broadcast_id=broadcast_id, updated_at=NOW)
    repository.mark_delivery(
        broadcast_id, "P1", status="sent", error_type=None, updated_at=NOW
    )

    recovered, recovered_rupor, recovered_main, _errors, recovered_repository = _build_service(
        tmp_path, participants=participants
    )
    recovered_count = recovered.resume_incomplete(occurred_at="2026-09-17T15:01:00+05:00")

    assert recovered_count == 1
    assert [(item.chat_id, item.text) for item in recovered_main.sent_messages] == [
        ("202", "После рестарта")
    ]
    assert main_bot.sent_messages == []
    assert recovered_repository.delivery_status(broadcast_id, "P1") == "sent"
    assert recovered_repository.delivery_status(broadcast_id, "P2") == "sent"
    assert recovered_repository.get_draft(101).status == "sent"
    assert recovered_rupor.sent_messages[-1].text.startswith("Рассылка завершена.")
    assert preview.buttons


def test_rupor_revalidates_consent_after_claim_before_each_send(tmp_path: Path) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, gateway_bot, main_bot, _error_bot, repository = _build_service(
        tmp_path, participants=participants
    )
    preview = service.receive_text(
        telegram_id=101, chat_id="101", text="Не должен прийти", occurred_at=NOW
    )
    original_claim = repository.claim_broadcast

    def revoke_after_claim(*args, **kwargs):
        claimed = original_claim(*args, **kwargs)
        service.sheets._participants[0]["consent_given"] = False
        return claimed

    repository.claim_broadcast = revoke_after_claim

    service.handle_callback(
        telegram_id=101,
        chat_id="101",
        callback_data=preview.buttons[0].callback_data,
        occurred_at=NOW,
    )

    broadcast_id = repository.get_draft(101).broadcast_id
    assert main_bot.sent_messages == []
    assert repository.delivery_status(broadcast_id, "P1") == "skipped"
    assert "Пропущено: 1" in gateway_bot.sent_messages[-1].text


def test_rupor_delivers_even_when_confirmation_audit_or_operator_reply_fails(
    tmp_path: Path,
) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, rupor_bot, main_bot, _error_bot, _repository = _build_service(
        tmp_path, participants=participants
    )
    preview = service.receive_text(
        telegram_id=101, chat_id="101", text="Надёжная отправка", occurred_at=NOW
    )
    service.repository.add_audit = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("audit"))
    original_send = rupor_bot.send_message

    def fail_confirmation(*, chat_id: str, text: str, **kwargs):
        if text.startswith("Рассылка запущена"):
            raise RuntimeError("control bot")
        return original_send(chat_id=chat_id, text=text, **kwargs)

    rupor_bot.send_message = fail_confirmation

    try:
        service.handle_callback(
            telegram_id=101,
            chat_id="101",
            callback_data=preview.buttons[0].callback_data,
            occurred_at=NOW,
        )
    except RuntimeError as exc:
        assert str(exc) == "control bot"

    assert [(item.chat_id, item.text) for item in main_bot.sent_messages] == [
        ("201", "Надёжная отправка")
    ]


def test_rupor_does_not_retry_after_sent_status_write_failure(tmp_path: Path) -> None:
    participants = [
        {"participant_id": "P1", "telegram_id": 201, "role": "participant", "status": "active", "consent_given": True},
    ]
    service, _rupor_bot, main_bot, _error_bot, repository = _build_service(
        tmp_path, participants=participants
    )
    preview = service.receive_text(
        telegram_id=101, chat_id="101", text="Один раз", occurred_at=NOW
    )
    original_mark = repository.mark_delivery

    def fail_sent_mark(broadcast_id, participant_id, *, status, error_type, updated_at):
        if status == "sent":
            raise RuntimeError("sqlite write")
        return original_mark(
            broadcast_id,
            participant_id,
            status=status,
            error_type=error_type,
            updated_at=updated_at,
        )

    repository.mark_delivery = fail_sent_mark
    service.handle_callback(
        telegram_id=101,
        chat_id="101",
        callback_data=preview.buttons[0].callback_data,
        occurred_at=NOW,
    )
    service.handle_start(telegram_id=101, chat_id="101", occurred_at=NOW)

    assert [(item.chat_id, item.text) for item in main_bot.sent_messages] == [("201", "Один раз")]
    broadcast_id = repository.get_draft(101).broadcast_id
    assert repository.delivery_status(broadcast_id, "P1") == "unknown"
