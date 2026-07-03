"""Voice message service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.services.participant_models import TelegramUserContext


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
