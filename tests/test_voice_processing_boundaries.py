from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient, FakeTelegramFileDownloader
from app.bot.messages import VOICE_PROCESSING_FAILED_TEXT, VOICE_TOO_LONG_TEXT
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


def test_mixed_text_and_voice_ordering_across_flows(tmp_path: Path) -> None:
    weekly_service, _weekly_downloader, weekly_transcriber, weekly_drafts, _insight_drafts, _error_bot = _service(
        tmp_path / "weekly",
        transcription_text="Голосовой отчёт",
    )
    _create_weekly_draft(weekly_drafts)
    weekly_drafts.append_text_message(USER.telegram_id, "Первое", occurred_at=NOW.isoformat(), telegram_message_id=501)
    weekly_service.handle_voice(_voice_input(telegram_file_id="weekly-file", telegram_message_id=502))
    weekly_drafts.append_text_message(USER.telegram_id, "Третье", occurred_at=NOW.isoformat(), telegram_message_id=503)

    insight_service, _insight_downloader, insight_transcriber, _weekly_drafts, insight_drafts, _error_bot = _service(
        tmp_path / "insight",
        transcription_text="Голосовой инсайт",
    )
    _create_insight_draft(insight_drafts)
    insight_drafts.append_text_message(USER.telegram_id, "Первое", occurred_at=NOW.isoformat(), telegram_message_id=501)
    insight_service.handle_voice(_voice_input(telegram_file_id="insight-file", telegram_message_id=502))
    insight_drafts.append_text_message(USER.telegram_id, "Третье", occurred_at=NOW.isoformat(), telegram_message_id=503)

    assert weekly_drafts.get_active_draft(USER.telegram_id).report_text == "Первое\nГолосовой отчёт\nТретье"
    assert insight_drafts.get_active_draft(USER.telegram_id).insight_text == "Первое\nГолосовой инсайт\nТретье"
    assert weekly_transcriber.requests == [
        TranscriptionRequest(
            audio_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_502.ogg"),
            duration_seconds=42,
        )
    ]
    assert insight_transcriber.requests == [
        TranscriptionRequest(
            audio_path=Path("data/audio/2026/week_03/personal_insights/P001/voice_1001_502.ogg"),
            duration_seconds=42,
        )
    ]


def test_over_limit_voice_has_no_side_effects(tmp_path: Path) -> None:
    service, downloader, transcriber, weekly_drafts, _insight_drafts, error_bot = _service(tmp_path)
    _create_weekly_draft(weekly_drafts)
    weekly_drafts.append_text_message(USER.telegram_id, "Текст до голосового", occurred_at=NOW.isoformat())

    response = service.handle_voice(_voice_input(duration_seconds=601))

    assert response.text == VOICE_TOO_LONG_TEXT
    assert response.accepted is False
    assert weekly_drafts.get_active_draft(USER.telegram_id).report_text == "Текст до голосового"
    assert downloader.downloads == []
    assert transcriber.requests == []
    assert error_bot.sent_messages == []


def test_voice_failure_routes_only_to_admin_error_chat(tmp_path: Path) -> None:
    service, downloader, transcriber, weekly_drafts, _insight_drafts, error_bot, main_bot, notification_bot = (
        _service_with_bots(tmp_path, transcriber=FailingSpeechTranscriber())
    )
    _create_weekly_draft(weekly_drafts)

    response = service.handle_voice(_voice_input())

    assert response.text == VOICE_PROCESSING_FAILED_TEXT
    assert response.accepted is False
    assert len(downloader.downloads) == 1
    assert transcriber.requests == [
        TranscriptionRequest(
            audio_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"),
            duration_seconds=42,
        )
    ]
    assert main_bot.sent_messages == []
    assert notification_bot.sent_messages == []
    assert [message.chat_id for message in error_bot.sent_messages] == ["admin-errors"]
    assert "voice_processing_failed" in error_bot.sent_messages[0].text
    assert "secret" not in error_bot.sent_messages[0].text.lower()
    assert "telegram-file-1" not in error_bot.sent_messages[0].text


def test_voice_artifacts_and_secrets_are_gitignored() -> None:
    ignored_entries = Path(".gitignore").read_text(encoding="utf-8").splitlines()

    for pattern in (".env", "*.key", "credentials.json", "secrets/", "data/audio/", "data/sqlite/"):
        assert pattern in ignored_entries


def _service(
    tmp_path: Path,
    *,
    transcription_text: str = "Расшифрованный голосовой фрагмент",
    transcriber: "RecordingSpeechTranscriber | FailingSpeechTranscriber | None" = None,
) -> tuple[
    VoiceMessageService,
    FakeTelegramFileDownloader,
    "RecordingSpeechTranscriber | FailingSpeechTranscriber",
    WeeklyReportDraftRepository,
    InsightDraftRepository,
    FakeBotClient,
]:
    service, downloader, speech_transcriber, weekly_drafts, insight_drafts, error_bot, _main_bot, _notification_bot = (
        _service_with_bots(tmp_path, transcription_text=transcription_text, transcriber=transcriber)
    )
    return service, downloader, speech_transcriber, weekly_drafts, insight_drafts, error_bot


def _service_with_bots(
    tmp_path: Path,
    *,
    transcription_text: str = "Расшифрованный голосовой фрагмент",
    transcriber: "RecordingSpeechTranscriber | FailingSpeechTranscriber | None" = None,
) -> tuple[
    VoiceMessageService,
    FakeTelegramFileDownloader,
    "RecordingSpeechTranscriber | FailingSpeechTranscriber",
    WeeklyReportDraftRepository,
    InsightDraftRepository,
    FakeBotClient,
    FakeBotClient,
    FakeBotClient,
]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    path_policy = StoragePathPolicy(audio_root=Path("data/audio"))
    downloader = FakeTelegramFileDownloader()
    speech_transcriber = transcriber or RecordingSpeechTranscriber(transcription_text=transcription_text)
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
    return service, downloader, speech_transcriber, weekly_drafts, insight_drafts, error_bot, main_bot, notification_bot


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


def _voice_input(
    *,
    telegram_file_id: str = "telegram-file-1",
    duration_seconds: int = 42,
    telegram_message_id: int = 501,
) -> VoiceMessageInput:
    return VoiceMessageInput(
        user=USER,
        telegram_file_id=telegram_file_id,
        duration_seconds=duration_seconds,
        telegram_message_id=telegram_message_id,
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
