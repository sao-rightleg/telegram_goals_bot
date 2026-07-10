---
status: planned
depends_on: []
wave: 1
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 4: Yandex SpeechKit transcriber

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Implement Yandex SpeechKit async recognition behind the existing synchronous `SpeechTranscriber` protocol. Existing voice business behavior must remain intact: only successful transcriptions are appended to active drafts, failed downloaded audio is deleted by the voice service, and admin errors stay sanitized.

This task must not change weekly-report or insight finalization rules.

## What to do

- Add a Yandex SpeechKit async transcriber class implementing `SpeechTranscriber`.
- Submit local audio, poll operation status with bounded timeout, and return `TranscriptionResult`.
- Map timeout, failed operation, empty result, invalid config, and HTTP errors to clear exceptions without secrets.
- Keep `FakeSpeechTranscriber` for tests.
- Add tests with mocked/fake HTTP responses; do not call Yandex live APIs.
- Ensure `MAX_VOICE_DURATION_SECONDS` remains the service-level 600-second limit.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_voice_processing_boundaries.py::test_yandex_transcriber_returns_text_from_completed_operation` - completed operation maps to `TranscriptionResult`.
- `tests/test_voice_processing_boundaries.py::test_yandex_transcriber_times_out_with_sanitized_error` - timeout raises safe error.
- `tests/test_voice_processing_boundaries.py::test_yandex_transcriber_failure_does_not_expose_credentials` - error text redacts credentials.
- `tests/test_voice_processing_service.py::test_transcription_failure_preserves_draft_and_notifies_admin` - existing failure behavior remains unchanged.

## Acceptance Criteria

- [ ] Yandex transcriber implements `SpeechTranscriber`.
- [ ] Polling uses bounded timeout and configurable poll interval.
- [ ] Successful Russian voice transcription returns text and original audio path.
- [ ] Timeout/failure/empty result raises a sanitized exception.
- [ ] Existing voice service success/failure tests still pass.
- [ ] No Yandex credential value is logged or included in exceptions.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/speech/transcription.py](/root/telegram_goals_bot/app/speech/transcription.py)
- [app/services/voice_messages.py](/root/telegram_goals_bot/app/services/voice_messages.py)
- [app/config.py](/root/telegram_goals_bot/app/config.py)
- [tests/test_voice_processing_service.py](/root/telegram_goals_bot/tests/test_voice_processing_service.py)
- [tests/test_voice_processing_boundaries.py](/root/telegram_goals_bot/tests/test_voice_processing_boundaries.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_voice_processing_service.py tests/test_voice_processing_boundaries.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_voice_processing_service.py tests/test_voice_processing_boundaries.py -v` -> all pass

## Details

**Files:**
- `app/speech/transcription.py` - add Yandex adapter, errors, and tests-facing construction.
- `tests/test_voice_processing_boundaries.py` - add adapter unit tests with fake HTTP.
- `tests/test_voice_processing_service.py` - keep current service behavior passing.
- `pyproject.toml` - add HTTP dependency if required by implementation.

**Dependencies:** None. Task 1 owns provider config selection; this task owns the transcriber implementation and should be constructible with explicit fake settings in tests.

**Edge cases:**
- Audio path missing or unreadable.
- Yandex operation never completes before timeout.
- Operation completes with no alternatives/text.
- HTTP failures during submit or poll.
- Secret-bearing auth headers must never be echoed.

**Implementation hints:**
- Keep the adapter synchronous from the caller perspective.
- Keep credential handling outside voice service; runtime composition injects a ready transcriber.
- Prefer small, testable helpers for request creation and result extraction.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-4/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-4/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-4/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
