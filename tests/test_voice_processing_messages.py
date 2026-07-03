from datetime import datetime, timezone

from app.bot.messages import (
    VOICE_ACCEPTED_TEXT,
    VOICE_NO_ACTIVE_DRAFT_TEXT,
    VOICE_PROCESSING_FAILED_TEXT,
    VOICE_TOO_LONG_TEXT,
)
from app.services.participant_models import TelegramUserContext
from app.services.voice_messages import VoiceMessageInput


def test_voice_processing_copy_matches_approved_text() -> None:
    assert VOICE_ACCEPTED_TEXT == "Голосовое принято и расшифровано."
    assert (
        VOICE_TOO_LONG_TEXT
        == "Голосовое длиннее 10 минут. Отправь, пожалуйста, более короткое голосовое или текст."
    )
    assert (
        VOICE_PROCESSING_FAILED_TEXT
        == "Не удалось распознать голосовое. Надиктуй ещё раз или напиши текстом для верности."
    )
    assert VOICE_NO_ACTIVE_DRAFT_TEXT == "Сначала начни отчёт или инсайт, потом отправь голосовое."

    for text in (
        VOICE_ACCEPTED_TEXT,
        VOICE_TOO_LONG_TEXT,
        VOICE_PROCESSING_FAILED_TEXT,
        VOICE_NO_ACTIVE_DRAFT_TEXT,
    ):
        assert "token" not in text.lower()
        assert "secret" not in text.lower()
        assert "participant_id" not in text
        assert "draft_" not in text


def test_voice_message_input_keeps_telegram_metadata() -> None:
    user = TelegramUserContext(telegram_id=1001, chat_id="chat-1", username="participant")
    now = datetime(2026, 7, 3, tzinfo=timezone.utc)

    request = VoiceMessageInput(
        user=user,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        telegram_message_id=501,
        now=now,
    )

    assert request.user is user
    assert request.telegram_file_id == "telegram-file-1"
    assert request.duration_seconds == 42
    assert request.telegram_message_id == 501
    assert request.now is now
