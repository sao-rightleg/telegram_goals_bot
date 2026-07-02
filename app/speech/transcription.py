"""Speech transcription boundary and fake implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


MAX_VOICE_DURATION_SECONDS = 600


@dataclass(frozen=True)
class TranscriptionRequest:
    audio_path: Path
    duration_seconds: int


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    audio_path: Path


class SpeechTranscriber(Protocol):
    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe an already stored local audio file."""


@dataclass(frozen=True)
class FakeSpeechTranscriber:
    transcription_text: str

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        if request.duration_seconds > MAX_VOICE_DURATION_SECONDS:
            raise ValueError("voice duration exceeds MVP limit")
        return TranscriptionResult(text=self.transcription_text, audio_path=request.audio_path)
