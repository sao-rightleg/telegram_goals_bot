"""Voice message service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.bot.clients import TelegramFileDownload, TelegramFileDownloader
from app.bot.messages import (
    VOICE_ACCEPTED_TEXT,
    VOICE_NO_ACTIVE_DRAFT_TEXT,
    VOICE_PROCESSING_FAILED_TEXT,
    VOICE_TOO_LONG_TEXT,
)
from app.services.notifications import NotificationCategory, NotificationRouter
from app.services.participant_models import TelegramUserContext
from app.speech.transcription import MAX_VOICE_DURATION_SECONDS, SpeechTranscriber, TranscriptionRequest
from app.storage.dialog_state import DialogStateRepository
from app.storage.insight_drafts import InsightDraftRepository
from app.storage.paths import StoragePathPolicy
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


@dataclass(frozen=True)
class VoiceMessageInput:
    user: TelegramUserContext
    telegram_file_id: str
    duration_seconds: int
    telegram_message_id: int | None
    now: datetime


@dataclass(frozen=True)
class StoredVoiceAttachment:
    local_file_path: Path
    transcription_text: str
    duration_seconds: int


@dataclass(frozen=True)
class VoiceMessageResult:
    text: str
    accepted: bool
    attachment: StoredVoiceAttachment | None = None


@dataclass(frozen=True)
class VoiceMessageService:
    dialog_states: DialogStateRepository
    weekly_report_drafts: WeeklyReportDraftRepository
    insight_drafts: InsightDraftRepository
    path_policy: StoragePathPolicy
    file_downloader: TelegramFileDownloader
    transcriber: SpeechTranscriber
    notification_router: NotificationRouter

    def handle_voice(self, request: VoiceMessageInput) -> VoiceMessageResult:
        state = self.dialog_states.get(request.user.telegram_id)
        if state is None or state.flow not in {"weekly_report", "insight"} or state.draft_id is None:
            return VoiceMessageResult(text=VOICE_NO_ACTIVE_DRAFT_TEXT, accepted=False)

        if request.duration_seconds > MAX_VOICE_DURATION_SECONDS:
            return VoiceMessageResult(text=VOICE_TOO_LONG_TEXT, accepted=False)

        draft = self._get_active_draft(request)
        if draft is None:
            return VoiceMessageResult(text=VOICE_NO_ACTIVE_DRAFT_TEXT, accepted=False)

        flow = state.flow
        destination_path = self._audio_path(
            request=request,
            participant_id=draft.participant_id,
            week_number=draft.week_number,
            team_slug=draft.team_id if flow == "weekly_report" else "personal_insights",
        )

        try:
            local_file_path = self.file_downloader.download_file(
                TelegramFileDownload(
                    telegram_file_id=request.telegram_file_id,
                    destination_path=destination_path,
                )
            )
            transcription = self.transcriber.transcribe(
                TranscriptionRequest(
                    audio_path=local_file_path,
                    duration_seconds=request.duration_seconds,
                )
            )
            self._append_transcription(
                flow=flow,
                request=request,
                local_file_path=local_file_path,
                transcription_text=transcription.text,
            )
        except Exception as error:
            self._notify_failure(
                request=request,
                flow=flow,
                participant_id=draft.participant_id,
                error=error,
            )
            return VoiceMessageResult(text=VOICE_PROCESSING_FAILED_TEXT, accepted=False)

        return VoiceMessageResult(
            text=VOICE_ACCEPTED_TEXT,
            accepted=True,
            attachment=StoredVoiceAttachment(
                local_file_path=local_file_path,
                transcription_text=transcription.text,
                duration_seconds=request.duration_seconds,
            ),
        )

    def _get_active_draft(self, request: VoiceMessageInput):
        state = self.dialog_states.get(request.user.telegram_id)
        if state is None:
            return None
        if state.flow == "weekly_report":
            return self.weekly_report_drafts.get_active_draft(request.user.telegram_id)
        if state.flow == "insight":
            return self.insight_drafts.get_active_draft(request.user.telegram_id)
        return None

    def _audio_path(
        self,
        *,
        request: VoiceMessageInput,
        participant_id: str,
        week_number: int,
        team_slug: str,
    ) -> Path:
        return self.path_policy.audio_path(
            year=request.now.year,
            week_number=week_number,
            team_slug=team_slug,
            participant_id=participant_id,
            file_name=_voice_file_name(request),
        )

    def _append_transcription(
        self,
        *,
        flow: str,
        request: VoiceMessageInput,
        local_file_path: Path,
        transcription_text: str,
    ) -> None:
        if flow == "weekly_report":
            self.weekly_report_drafts.append_voice_transcription(
                request.user.telegram_id,
                telegram_file_id=request.telegram_file_id,
                local_file_path=local_file_path,
                duration_seconds=request.duration_seconds,
                transcription_text=transcription_text,
                occurred_at=request.now.isoformat(),
                telegram_message_id=request.telegram_message_id,
            )
            return

        self.insight_drafts.append_voice_transcription(
            request.user.telegram_id,
            telegram_file_id=request.telegram_file_id,
            local_file_path=local_file_path,
            duration_seconds=request.duration_seconds,
            transcription_text=transcription_text,
            occurred_at=request.now.isoformat(),
            telegram_message_id=request.telegram_message_id,
        )

    def _notify_failure(
        self,
        *,
        request: VoiceMessageInput,
        flow: str,
        participant_id: str,
        error: Exception,
    ) -> None:
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=(
                "voice_processing_failed "
                f"flow={flow} "
                f"telegram_id={request.user.telegram_id} "
                f"participant_id={participant_id} "
                f"error_type={type(error).__name__} "
                f"occurred_at={request.now.isoformat()}"
            ),
            recipients=(),
        )


def _voice_file_name(request: VoiceMessageInput) -> str:
    suffix = request.telegram_message_id
    if suffix is None:
        suffix = int(request.now.timestamp())
    return f"voice_{request.user.telegram_id}_{suffix}.ogg"
