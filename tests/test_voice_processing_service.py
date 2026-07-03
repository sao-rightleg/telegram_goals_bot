from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient, FakeTelegramFileDownloader
from app.bot.messages import (
    VOICE_ACCEPTED_TEXT,
    VOICE_NO_ACTIVE_DRAFT_TEXT,
    VOICE_PROCESSING_FAILED_TEXT,
    VOICE_TOO_LONG_TEXT,
)
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_models import TelegramUserContext
from app.services.voice_messages import VoiceMessageInput, VoiceMessageService
from app.speech.transcription import TranscriptionRequest, TranscriptionResult
from app.storage.dialog_state import DialogStateRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.paths import StoragePathPolicy
from app.storage.sqlite import initialize_schema
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))
USER = TelegramUserContext(telegram_id=1001, chat_id="chat-1001", username="p001")


def test_rejects_voice_without_active_draft_without_download(tmp_path: Path) -> None:
    service, downloader, transcriber, _weekly_drafts, _insight_drafts, _error_bot = _service(tmp_path)

    response = service.handle_voice(_voice_input())

    assert response.text == VOICE_NO_ACTIVE_DRAFT_TEXT
    assert response.accepted is False
    assert response.attachment is None
    assert downloader.downloads == []
    assert transcriber.requests == []


def test_rejects_over_limit_voice_before_download(tmp_path: Path) -> None:
    service, downloader, transcriber, weekly_drafts, _insight_drafts, _error_bot = _service(tmp_path)
    _create_weekly_draft(weekly_drafts)

    response = service.handle_voice(_voice_input(duration_seconds=601))

    assert response.text == VOICE_TOO_LONG_TEXT
    assert response.accepted is False
    assert weekly_drafts.get_active_draft(USER.telegram_id).report_text == ""
    assert downloader.downloads == []
    assert transcriber.requests == []


def test_accepts_weekly_report_voice_into_draft(tmp_path: Path) -> None:
    service, downloader, transcriber, weekly_drafts, _insight_drafts, _error_bot = _service(tmp_path)
    _create_weekly_draft(weekly_drafts)

    response = service.handle_voice(_voice_input())

    draft = weekly_drafts.get_active_draft(USER.telegram_id)
    assert response.text == VOICE_ACCEPTED_TEXT
    assert response.accepted is True
    assert response.attachment is not None
    assert draft is not None
    assert draft.report_text == "Расшифрованный голосовой фрагмент"
    assert downloader.downloads[0].telegram_file_id == "telegram-file-1"
    assert downloader.downloads[0].destination_path == response.attachment.local_file_path
    assert transcriber.requests == [
        TranscriptionRequest(audio_path=response.attachment.local_file_path, duration_seconds=42)
    ]
    assert response.attachment.local_file_path == Path(
        "data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"
    )


def test_accepts_insight_voice_into_draft(tmp_path: Path) -> None:
    service, downloader, _transcriber, _weekly_drafts, insight_drafts, _error_bot = _service(tmp_path)
    _create_insight_draft(insight_drafts)

    response = service.handle_voice(_voice_input())

    draft = insight_drafts.get_active_draft(USER.telegram_id)
    assert response.text == VOICE_ACCEPTED_TEXT
    assert response.accepted is True
    assert draft is not None
    assert draft.insight_text == "Расшифрованный голосовой фрагмент"
    assert downloader.downloads[0].destination_path == Path(
        "data/audio/2026/week_03/personal_insights/P001/voice_1001_501.ogg"
    )


def test_transcription_failure_preserves_draft_and_notifies_admin(tmp_path: Path) -> None:
    service, downloader, transcriber, weekly_drafts, _insight_drafts, error_bot = _service(
        tmp_path,
        transcriber=FailingSpeechTranscriber(),
    )
    _create_weekly_draft(weekly_drafts)
    weekly_drafts.append_text_message(USER.telegram_id, "Уже есть текст", occurred_at=NOW.isoformat())

    response = service.handle_voice(_voice_input())

    draft = weekly_drafts.get_active_draft(USER.telegram_id)
    assert response.text == VOICE_PROCESSING_FAILED_TEXT
    assert response.accepted is False
    assert response.attachment is None
    assert draft is not None
    assert draft.report_text == "Уже есть текст"
    assert len(downloader.downloads) == 1
    assert transcriber.requests == [
        TranscriptionRequest(
            audio_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"),
            duration_seconds=42,
        )
    ]
    assert len(error_bot.sent_messages) == 1
    assert "voice_processing_failed" in error_bot.sent_messages[0].text
    assert "telegram_id=1001" in error_bot.sent_messages[0].text
    assert "Расшифрованный" not in error_bot.sent_messages[0].text


def _service(
    tmp_path: Path,
    *,
    transcriber: "RecordingSpeechTranscriber | FailingSpeechTranscriber | None" = None,
) -> tuple[
    VoiceMessageService,
    FakeTelegramFileDownloader,
    "RecordingSpeechTranscriber | FailingSpeechTranscriber",
    WeeklyReportDraftRepository,
    InsightDraftRepository,
    FakeBotClient,
]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    path_policy = StoragePathPolicy(audio_root=Path("data/audio"))
    downloader = FakeTelegramFileDownloader()
    speech_transcriber = transcriber or RecordingSpeechTranscriber(
        transcription_text="Расшифрованный голосовой фрагмент"
    )
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    weekly_drafts = WeeklyReportDraftRepository(db_path)
    insight_drafts = InsightDraftRepository(db_path)
    service = VoiceMessageService(
        dialog_states=DialogStateRepository(db_path),
        weekly_report_drafts=weekly_drafts,
        insight_drafts=insight_drafts,
        path_policy=path_policy,
        file_downloader=downloader,
        transcriber=speech_transcriber,
        notification_router=router,
    )
    return service, downloader, speech_transcriber, weekly_drafts, insight_drafts, error_bot


def _create_weekly_draft(repository: WeeklyReportDraftRepository) -> None:
    repository.create_draft(
        draft_id="weekly-draft-1",
        telegram_id=USER.telegram_id,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=4,
        occurred_at=NOW.isoformat(),
    )


def _create_insight_draft(repository: InsightDraftRepository) -> None:
    repository.create_draft(
        draft_id="insight-draft-1",
        telegram_id=USER.telegram_id,
        participant_id="P001",
        goal_id="G001",
        week_number=3,
        occurred_at=NOW.isoformat(),
    )


def _voice_input(*, duration_seconds: int = 42) -> VoiceMessageInput:
    return VoiceMessageInput(
        user=USER,
        telegram_file_id="telegram-file-1",
        duration_seconds=duration_seconds,
        telegram_message_id=501,
        now=NOW,
    )


@dataclass
class RecordingSpeechTranscriber:
    transcription_text: str
    requests: list[TranscriptionRequest] = field(default_factory=list)

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        self.requests.append(request)
        return TranscriptionResult(text=self.transcription_text, audio_path=request.audio_path)


@dataclass
class FailingSpeechTranscriber:
    requests: list[TranscriptionRequest] = field(default_factory=list)

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        self.requests.append(request)
        raise RuntimeError("speech provider unavailable")
