"""Speech transcription boundary and fake implementation."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Protocol

import httpx


MAX_VOICE_DURATION_SECONDS = 600
YANDEX_STT_BASE_URL = "https://stt.api.cloud.yandex.net"
YANDEX_OPERATIONS_BASE_URL = "https://operation.api.cloud.yandex.net"


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


class YandexSpeechKitError(RuntimeError):
    """Raised when Yandex SpeechKit cannot produce a safe transcription result."""


@dataclass(frozen=True)
class YandexSpeechKitTranscriber:
    api_key: str | None
    folder_id: str
    http_client: httpx.Client
    operation_timeout_seconds: float
    poll_interval_seconds: float
    iam_token: str | None = None
    stt_base_url: str = YANDEX_STT_BASE_URL
    operations_base_url: str = YANDEX_OPERATIONS_BASE_URL

    def __post_init__(self) -> None:
        if not self.folder_id:
            raise YandexSpeechKitError("Yandex SpeechKit configuration is invalid: missing folder id")
        if not self.api_key and not self.iam_token:
            raise YandexSpeechKitError("Yandex SpeechKit configuration is invalid: missing credentials")
        if self.operation_timeout_seconds <= 0:
            raise YandexSpeechKitError("Yandex SpeechKit configuration is invalid: timeout must be positive")
        if self.poll_interval_seconds <= 0:
            raise YandexSpeechKitError(
                "Yandex SpeechKit configuration is invalid: poll interval must be positive"
            )

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        if not request.audio_path.exists() or not request.audio_path.is_file():
            raise YandexSpeechKitError("Yandex SpeechKit audio file is missing")

        operation_id = self._submit(request.audio_path)
        self._wait_for_completion(operation_id)
        text = self._get_recognition_text(operation_id)
        return TranscriptionResult(text=text, audio_path=request.audio_path)

    def _submit(self, audio_path: Path) -> str:
        audio_content = base64.b64encode(audio_path.read_bytes()).decode("ascii")
        payload = {
            "content": audio_content,
            "recognition_model": {
                "model": "general",
                "audio_format": {
                    "container_audio": {
                        "container_audio_type": "OGG_OPUS",
                    },
                },
                "language_restriction": {
                    "restriction_type": "WHITELIST",
                    "language_code": ["ru-RU"],
                },
            },
        }
        response = self._request(
            "POST",
            f"{self.stt_base_url}/stt/v3/recognizeFileAsync",
            json=payload,
        )
        operation_id = response.get("id")
        if not isinstance(operation_id, str) or not operation_id:
            raise YandexSpeechKitError("Yandex SpeechKit response is invalid: missing operation id")
        return operation_id

    def _wait_for_completion(self, operation_id: str) -> None:
        deadline = time.monotonic() + self.operation_timeout_seconds
        while True:
            operation = self._request(
                "GET",
                f"{self.operations_base_url}/operations/{operation_id}",
            )
            error = operation.get("error")
            if error:
                raise YandexSpeechKitError(
                    self._sanitize(f"Yandex SpeechKit operation failed: {_error_text(error)}")
                )
            if operation.get("done") is True:
                return
            if time.monotonic() >= deadline:
                raise YandexSpeechKitError("Yandex SpeechKit operation timed out")
            time.sleep(min(self.poll_interval_seconds, max(deadline - time.monotonic(), 0)))

    def _get_recognition_text(self, operation_id: str) -> str:
        response = self._request(
            "GET",
            f"{self.stt_base_url}/stt/v3/getRecognition",
            params={"operation_id": operation_id},
        )
        text = _extract_text(response)
        if not text:
            raise YandexSpeechKitError("Yandex SpeechKit response is empty")
        return text

    def _request(self, method: str, url: str, **kwargs: object) -> dict[str, object]:
        try:
            response = self.http_client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.HTTPError as exc:
            raise YandexSpeechKitError(
                self._sanitize(f"Yandex SpeechKit request failed: {type(exc).__name__}")
            ) from exc

        if response.status_code >= 400:
            raise YandexSpeechKitError(
                self._sanitize(
                    f"Yandex SpeechKit request failed: status={response.status_code} "
                    f"message={_response_message(response)}"
                )
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise YandexSpeechKitError("Yandex SpeechKit response is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise YandexSpeechKitError("Yandex SpeechKit response is invalid")
        return payload

    def _headers(self) -> dict[str, str]:
        authorization = f"Bearer {self.iam_token}" if self.iam_token else f"Api-Key {self.api_key}"
        return {
            "Authorization": authorization,
            "x-folder-id": self.folder_id,
        }

    def _sanitize(self, message: str) -> str:
        redacted = message
        for secret in (self.api_key, self.iam_token, self.folder_id):
            if secret:
                redacted = redacted.replace(secret, "[REDACTED]")
        return redacted


@dataclass(frozen=True)
class FakeSpeechTranscriber:
    transcription_text: str

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        if request.duration_seconds > MAX_VOICE_DURATION_SECONDS:
            raise ValueError("voice duration exceeds MVP limit")
        return TranscriptionResult(text=self.transcription_text, audio_path=request.audio_path)


def _extract_text(payload: dict[str, object]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        return ""

    alternatives = _alternatives_from_result(result)
    texts = [
        alternative.get("text", "").strip()
        for alternative in alternatives
        if isinstance(alternative, dict) and isinstance(alternative.get("text"), str)
    ]
    return "\n".join(text for text in texts if text).strip()


def _alternatives_from_result(result: dict[object, object]) -> list[object]:
    final = result.get("final")
    if isinstance(final, dict):
        alternatives = final.get("alternatives")
        if isinstance(alternatives, list):
            return alternatives

    final_refinement = result.get("finalRefinement")
    if isinstance(final_refinement, dict):
        normalized_text = final_refinement.get("normalizedText")
        if isinstance(normalized_text, dict):
            alternatives = normalized_text.get("alternatives")
            if isinstance(alternatives, list):
                return alternatives

    return []


def _response_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if isinstance(message, str):
            return message
    return response.text[:200]


def _error_text(error: object) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
        code = error.get("code")
        if code is not None:
            return f"code={code}"
    return str(error)
