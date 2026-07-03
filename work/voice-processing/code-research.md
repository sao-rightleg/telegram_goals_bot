# Code Research: voice-processing

## Scope

Research for adding voice message handling to existing Telegram draft flows without adding live SDK integrations or changing MVP storage boundaries.

## Relevant Current Code

- `app/speech/transcription.py`
  - Defines `MAX_VOICE_DURATION_SECONDS = 600`.
  - Defines `TranscriptionRequest`, `TranscriptionResult`, `SpeechTranscriber`, and `FakeSpeechTranscriber`.
  - Current fake transcriber rejects duration greater than the MVP limit.
- `app/storage/paths.py`
  - Defines `StoragePathPolicy.audio_path(...)`.
  - Builds local paths under `data/audio/{year}/week_{week_number}/{team_slug}/{participant_id}/{file_name}`.
  - Rejects empty fragments, public URL-like fragments, absolute paths, path traversal, and multi-part fragments.
- `app/storage/sqlite.py`
  - Defines `draft_attachments` with `duration_seconds <= 600`, `local_file_path`, `telegram_file_id`, `transcription_status`, `transcription_text`, and `error_message`.
  - Defines `draft_messages` with ordered `message_type` values including `voice_transcription`.
  - Defines scheduler job type `audio_cleanup`, but no cleanup repository/job implementation exists yet.
- `app/storage/weekly_report_drafts.py`
  - Owns weekly report draft lifecycle and ordered text message persistence.
  - Voice support should extend or reuse its message/attachment behavior without making SQLite a final business store.
- `app/storage/insight_drafts.py`
  - Owns insight draft lifecycle and already purges full draft text after successful save.
  - Voice support must preserve this privacy boundary after insight save.
- `app/services/weekly_reports.py`
  - Owns weekly report status, deadline, duplicate, selected-step, and final Sheets save rules.
  - Voice processing should add draft fragments only; final status-changing rules must remain here.
- `app/services/insights.py`
  - Owns insight add/list/final save rules.
  - Voice processing should not affect weekly status or progress.
- `app/sheets/gateway.py`
  - Fake Sheets gateway already has final weekly report and insight write paths with transcription/audio fields represented in docs-level schema. Tech spec must confirm any protocol method changes needed.
- `app/bot/clients.py`
  - Bot client boundary currently covers send operations. Telegram file download is not yet represented and will need a boundary before implementation.

## Existing Tests To Reuse

- `tests/test_storage_paths.py`
- `tests/test_sqlite_schema.py`
- `tests/test_weekly_report_draft_repository.py`
- `tests/test_weekly_report_finalize.py`
- `tests/test_insight_draft_repository.py`
- `tests/test_insight_add_flow.py`
- `tests/test_insight_boundaries.py`
- `tests/test_boundaries.py`

## Integration Direction

Voice handling should be implemented as an input capability for active draft flows:

1. Validate known user and consent through existing participant flow gates.
2. Require an active weekly report, insight, or captain manual draft.
3. Validate duration before local save/transcription.
4. Download Telegram file through a new or extended Telegram file boundary.
5. Save audio through `StoragePathPolicy.audio_path(...)`.
6. Transcribe through `SpeechTranscriber`.
7. Store attachment metadata and ordered `voice_transcription` draft message.
8. Leave final Google Sheets write to the existing weekly report or insight finalization service.

## Risks

- `draft_attachments` schema exists, but repositories do not yet expose attachment operations.
- Telegram file download boundary does not exist yet.
- Need to avoid duplicating final save behavior in voice service.
- Need to preserve insight post-save text cleanup.
- Real transcription provider setup is deployment/config work and should not be required for local unit tests.

## Recommended Feature Size

M: several components are involved, but this is not a new architecture. Expected implementation touches speech boundary, Telegram file boundary, storage repositories, weekly report/insight services, and tests.
