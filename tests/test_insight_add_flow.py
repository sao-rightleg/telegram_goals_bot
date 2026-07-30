from datetime import datetime
from dataclasses import replace
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import MenuAction
from app.bot.messages import (
    CONSENT_TEXT,
    INSIGHT_DONE_BUTTON,
    INSIGHT_DUPLICATE_TEXT,
    INSIGHT_EMPTY_TEXT,
    INSIGHT_MISSING_ACTIVE_GOAL_TEXT,
    INSIGHT_MISSING_TEXT,
    INSIGHT_SUCCESS_TEXT,
    INSIGHT_TITLE_PROMPT_TEXT,
    INSIGHT_TITLE_TOO_LONG_TEXT,
    INSIGHT_VOICE_NOT_AVAILABLE_TEXT,
    VOICE_ACCEPTED_TEXT,
    UNKNOWN_USER_TEXT,
    build_insight_menu_buttons,
)
from app.scheduler.calendar import current_challenge_week_number
from app.services.insights import InsightService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.services.voice_messages import StoredVoiceAttachment, VoiceMessageInput, VoiceMessageResult
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.sqlite import initialize_schema


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
LATER = datetime(2026, 7, 2, 10, 5, tzinfo=ZoneInfo("Asia/Yekaterinburg"))
USER = TelegramUserContext(telegram_id=1001, chat_id="chat-1001")


def test_insight_menu_is_available_from_view_insights(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot, _notification_bot = _build_participant_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
    )

    response = service.handle_menu_action(USER, MenuAction.VIEW_INSIGHTS, occurred_at=_iso(NOW))

    assert response.buttons == build_insight_menu_buttons()
    assert response.text == "Мои инсайты"
    assert main_bot.sent_messages[-1].text == "Мои инсайты"


def test_current_week_text_insight_is_saved_to_sheets(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Первое сообщение", now=NOW, telegram_message_id=501)
    service.add_text_message(USER, "Второе сообщение", now=LATER, telegram_message_id=502)
    prompt = service.request_title(USER, now=LATER)
    response = service.set_title_and_save(USER, "Короткий заголовок", now=LATER)

    insights = gateway.list_insights()
    week_number = current_challenge_week_number(NOW)
    assert prompt.text == INSIGHT_TITLE_PROMPT_TEXT
    assert response.text == INSIGHT_SUCCESS_TEXT
    assert response.menu_items
    assert len(insights) == 1
    assert str(insights[0]["insight_id"]).startswith(f"I-P001-{week_number:02d}-")
    assert insights[0]["participant_id"] == "P001"
    assert insights[0]["goal_id"] == "G001"
    assert insights[0]["week_number"] == week_number
    assert insights[0]["insight_scope"] == "current_week"
    assert insights[0]["insight_title"] == "Короткий заголовок"
    assert insights[0]["insight_date"] == "2026-07-02"
    assert insights[0]["insight_text"] == "Первое сообщение\nВторое сообщение"
    assert insights[0]["created_by_id"] == "P001"
    assert insights[0]["created_by_role"] == "participant"
    assert drafts.get_active_draft(1001) is None


def test_request_title_marks_draft_as_awaiting_title(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Инсайт текстом", now=NOW, telegram_message_id=501)
    response = service.request_title(USER, now=LATER)

    assert response.text == INSIGHT_TITLE_PROMPT_TEXT
    assert _dialog_step(drafts, USER.telegram_id) == "awaiting_title"


def test_voice_insight_final_save_includes_transcription_and_audio_path(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    drafts.append_voice_transcription(
        USER.telegram_id,
        telegram_file_id="telegram-file-1",
        local_file_path=Path("data/audio/2026/week_04/personal_insights/P001/voice_1001_501.ogg"),
        duration_seconds=42,
        transcription_text="Голосовой инсайт",
        occurred_at=NOW.isoformat(),
        telegram_message_id=501,
    )
    response = service.set_title_and_save(USER, "Голосовой заголовок", now=LATER)

    row = gateway.list_insights()[0]
    assert response.text == INSIGHT_SUCCESS_TEXT
    assert row["insight_text"] == "Голосовой инсайт"
    assert row["transcription_text"] == "Голосовой инсайт"
    assert row["audio_file_path"] == "data/audio/2026/week_04/personal_insights/P001/voice_1001_501.ogg"
    assert row["audio_deleted_at"] == ""
    assert drafts.get_active_draft(1001) is None


def test_mixed_text_and_voice_insight_preserves_order(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Первое", now=NOW, telegram_message_id=501)
    drafts.append_voice_transcription(
        USER.telegram_id,
        telegram_file_id="telegram-file-1",
        local_file_path=Path("data/audio/2026/week_04/personal_insights/P001/voice_1001_502.ogg"),
        duration_seconds=42,
        transcription_text="Голосом второе",
        occurred_at=LATER.isoformat(),
        telegram_message_id=502,
    )
    service.add_text_message(USER, "Третье", now=LATER, telegram_message_id=503)
    service.set_title_and_save(USER, "Смешанный инсайт", now=LATER)

    row = gateway.list_insights()[0]
    full_text = service.get_full_text(USER, insight_id=str(row["insight_id"]), now=LATER)
    list_response = service.list_insights(USER, page_index=0, now=LATER)
    assert row["insight_text"] == "Первое\nГолосом второе\nТретье"
    assert row["transcription_text"] == "Голосом второе"
    assert row["audio_file_path"] == "data/audio/2026/week_04/personal_insights/P001/voice_1001_502.ogg"
    assert row["audio_deleted_at"] == ""
    assert "Первое" in full_text.text
    assert "Голосом второе" in full_text.text
    assert "Третье" in full_text.text
    assert "Первое" in list_response.text
    assert "Голосом второе" in list_response.text
    assert "Третье" in list_response.text


def test_missing_active_goal_blocks_save_with_custom_copy(tmp_path: Path) -> None:
    service, gateway, _main_bot, error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[],
    )

    response = service.start_add(USER, now=NOW)

    assert response.text == INSIGHT_MISSING_ACTIVE_GOAL_TEXT
    assert gateway.list_insights() == []
    assert len(error_bot.sent_messages) == 1
    assert "missing_required_data" in error_bot.sent_messages[0].text
    assert "active_goal" in error_bot.sent_messages[0].text


def test_empty_finalize_keeps_draft_and_asks_for_text(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    response = service.request_title(USER, now=LATER)

    assert response.text == INSIGHT_EMPTY_TEXT
    assert gateway.list_insights() == []
    assert drafts.get_active_draft(1001) is not None


def test_title_over_limit_is_rejected(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Текст инсайта", now=NOW)
    response = service.set_title_and_save(USER, "а" * 121, now=LATER)

    assert response.text == INSIGHT_TITLE_TOO_LONG_TEXT
    assert gateway.list_insights() == []
    assert drafts.get_active_draft(1001) is not None


def test_skip_title_saves_empty_title(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )
    text = (
        "Сегодня я понял, что мне не хватает планирования, потому что утро снова "
        "уходит в ежедневную рутину и я забываю про цель."
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, text, now=NOW)
    response = service.skip_title_and_save(USER, now=LATER)

    assert response.text == INSIGHT_SUCCESS_TEXT
    assert gateway.list_insights()[0]["insight_title"] == ""


def test_cancel_clears_draft_without_saving(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    response = service.cancel(USER, now=LATER)

    assert response.menu_items
    assert gateway.list_insights() == []
    assert drafts.get_active_draft(1001) is None


def test_duplicate_finalization_is_idempotent(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Текст инсайта", now=NOW)
    first = service.set_title_and_save(USER, "Заголовок", now=LATER)
    second = service.set_title_and_save(USER, "Заголовок", now=LATER)

    assert first.text == INSIGHT_SUCCESS_TEXT
    assert second.text == INSIGHT_DUPLICATE_TEXT
    assert len(gateway.list_insights()) == 1


def test_multiple_current_week_insights_are_saved_with_distinct_callbacks(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )

    service.start_add(USER, now=NOW)
    service.add_text_message(USER, "Первый инсайт недели", now=NOW)
    first = service.set_title_and_save(USER, "Первый", now=LATER)
    service.start_add(USER, now=LATER)
    service.add_text_message(USER, "Второй инсайт недели", now=LATER)
    second = service.set_title_and_save(USER, "Второй", now=LATER)

    insights = gateway.list_insights()
    insight_ids = {row["insight_id"] for row in insights}
    assert first.text == INSIGHT_SUCCESS_TEXT
    assert second.text == INSIGHT_SUCCESS_TEXT
    assert len(insights) == 2
    assert len(insight_ids) == 2
    assert {row["insight_text"] for row in insights} == {"Первый инсайт недели", "Второй инсайт недели"}
    for row in insights:
        full_text = service.get_full_text(USER, insight_id=str(row["insight_id"]), now=LATER)
        assert row["insight_text"] in full_text.text


def test_unknown_user_cannot_use_insight_service(tmp_path: Path) -> None:
    service, gateway, main_bot, error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[],
        goals=[],
    )
    unknown = TelegramUserContext(telegram_id=9999, chat_id="chat-9999", username="unknown-user")

    add_response = service.start_add(unknown, now=NOW)
    list_response = service.list_insights(unknown, page_index=0, now=NOW)
    full_response = service.get_full_text(unknown, insight_id="I001", now=NOW)

    assert add_response.text == UNKNOWN_USER_TEXT
    assert list_response.text == UNKNOWN_USER_TEXT
    assert full_response.text == UNKNOWN_USER_TEXT
    assert gateway.list_insights() == []
    assert len(error_bot.sent_messages) == 3
    assert all("unknown_telegram_user" in message.text for message in error_bot.sent_messages)
    assert main_bot.sent_messages[-1].text == UNKNOWN_USER_TEXT


def test_non_consenting_user_cannot_add_list_or_open_insights(tmp_path: Path) -> None:
    service, gateway, _main_bot, error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001, consent_given=False)],
        goals=[_goal("G001", "P001")],
    )
    gateway.append_insight(
        {
            "insight_id": "I001",
            "participant_id": "P001",
            "goal_id": "G001",
            "week_number": 4,
            "insight_scope": "current_week",
            "insight_title": "Скрытый инсайт",
            "insight_date": "2026-07-02",
            "insight_text": "Скрытый полный текст",
            "created_by_id": "P001",
            "created_by_role": "participant",
            "created_at": "2026-07-02T10:00:00+05:00",
        }
    )

    add_response = service.start_add(USER, now=NOW)
    list_response = service.list_insights(USER, page_index=0, now=NOW)
    full_response = service.get_full_text(USER, insight_id="I001", now=NOW)

    assert add_response.text == CONSENT_TEXT
    assert list_response.text == CONSENT_TEXT
    assert full_response.text == CONSENT_TEXT
    sent_text = "\n".join(message.text for message in service.main_bot.sent_messages)
    assert "Скрытый полный текст" not in sent_text
    assert error_bot.sent_messages == []
    assert len(gateway.list_insights()) == 1


def test_voice_message_appends_to_insight_draft(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot, _notification_bot, _drafts = _build_insight_service(
        tmp_path,
        participants=[_participant("P001", 1001)],
        goals=[_goal("G001", "P001")],
    )
    service = replace(service, voice_messages=AcceptingVoiceService(drafts=_drafts))
    service.start_add(USER, now=NOW)

    response = service.add_voice_message(
        USER,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        now=NOW,
        telegram_message_id=501,
    )

    assert response.text == VOICE_ACCEPTED_TEXT
    assert _drafts.get_active_draft(1001).insight_text == "Голосовой инсайт"
    assert gateway.list_insights() == []


def _build_insight_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    goals: list[dict[str, object]],
) -> tuple[InsightService, FakeSheetsGateway, FakeBotClient, FakeBotClient, FakeBotClient, InsightDraftRepository]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(participants=participants, goals=goals)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    drafts = InsightDraftRepository(db_path)
    return (
        InsightService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            drafts=drafts,
        ),
        gateway,
        main_bot,
        error_bot,
        notification_bot,
        drafts,
    )


def _build_participant_service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
) -> tuple[ParticipantFlowService, FakeSheetsGateway, FakeBotClient, FakeBotClient, FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(participants=participants)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return (
        ParticipantFlowService(
            sheets=gateway,
            main_bot=main_bot,
            notification_router=router,
            dialog_states=DialogStateRepository(db_path),
        ),
        gateway,
        main_bot,
        error_bot,
        notification_bot,
    )


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    role: str = "participant",
    consent_given: bool = True,
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "role": role,
        "team_id": "T001",
        "consent_given": consent_given,
    }


def _goal(goal_id: str, participant_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": "Цель",
        "goal_status": "active",
    }


def _dialog_step(drafts: InsightDraftRepository, telegram_id: int) -> str:
    with sqlite3.connect(drafts._db_path) as connection:
        row = connection.execute(
            "SELECT step FROM dialog_states WHERE telegram_id = ?",
            (telegram_id,),
        ).fetchone()
    assert row is not None
    return str(row[0])


def _iso(value: datetime) -> str:
    return value.isoformat()


class AcceptingVoiceService:
    def __init__(self, drafts: InsightDraftRepository) -> None:
        self._drafts = drafts

    def handle_voice(self, request: VoiceMessageInput) -> VoiceMessageResult:
        self._drafts.append_voice_transcription(
            request.user.telegram_id,
            telegram_file_id=request.telegram_file_id,
            local_file_path=Path("data/audio/2026/week_04/personal_insights/P001/voice_1001_501.ogg"),
            duration_seconds=request.duration_seconds,
            transcription_text="Голосовой инсайт",
            occurred_at=request.now.isoformat(),
            telegram_message_id=request.telegram_message_id,
        )
        return VoiceMessageResult(
            text=VOICE_ACCEPTED_TEXT,
            accepted=True,
            attachment=StoredVoiceAttachment(
                local_file_path=Path("data/audio/2026/week_04/personal_insights/P001/voice_1001_501.ogg"),
                transcription_text="Голосовой инсайт",
                duration_seconds=request.duration_seconds,
            ),
        )
