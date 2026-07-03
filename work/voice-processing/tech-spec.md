---
created: 2026-07-03
status: draft
branch: dev
size: M
---

# Tech Spec: voice-processing

## Solution

Implement voice messages as an input capability for active draft flows, not as a separate user flow. The feature will replace the current weekly-report and insight "voice not available" branches with a shared service that validates duration, downloads the Telegram file through a boundary, stores it through the existing local storage path policy, transcribes it through the speech boundary, and appends the transcription to the active draft in message order.

Final business writes stay owned by existing flow services. Weekly report finalization continues to enforce consent, deadline, duplicate report, status, selected-step, and planned-step closure rules. Insight finalization continues to keep insights separate from weekly progress and clears personal draft text after successful save.

The implementation remains fake/local-boundary based. It will not add a live Telegram SDK, real transcription SDK, deployment workflow, public audio URLs, Docker, Redis, Celery, PostgreSQL, or a production cleanup scheduler in this feature.

## Architecture

### What we're building/modifying

- **Telegram file boundary** — a small adapter-independent protocol in `app/bot/clients.py` for downloading a Telegram voice file to a caller-provided local path, plus a fake downloader for tests.
- **Voice message models and service** — a new service module, expected as `app/services/voice_messages.py`, that receives voice metadata and routes it to the active weekly report or insight draft.
- **Draft repository voice operations** — extensions to `WeeklyReportDraftRepository` and `InsightDraftRepository` for storing draft attachment metadata and ordered `voice_transcription` draft messages.
- **Speech boundary hardening** — keep `MAX_VOICE_DURATION_SECONDS = 600` and fake transcriber behavior as the single local duration contract.
- **Weekly report integration** — replace `WeeklyReportService.reject_voice_message(...)` with voice processing that appends to the active report draft.
- **Insight integration** — replace `InsightService.reject_voice_message(...)` with voice processing that appends to the active insight draft.
- **Russian copy constants** — add approved success, too-long, and retry/failure copy in `app/bot/messages.py`.
- **Tests** — add focused voice-processing tests and extend existing weekly report, insight, storage path, schema, and boundary regressions.

### How it works

1. A Telegram handler receives a voice message while the user is in an active draft flow.
2. Handler builds a voice input request with Telegram user context, Telegram file id, duration seconds, original Telegram message id, and current time.
3. `VoiceMessageService` reads `DialogStateRepository.get(telegram_id)` to determine the active flow.
4. If no active voice-capable flow exists, the service returns a calm "start a report or insight first" response and does not download the file.
5. If `duration_seconds > 600`, the service returns the approved too-long message and does not download, store, transcribe, or mutate draft state.
6. For `weekly_report`, the service loads `WeeklyReportDraftRepository.get_active_draft(...)`; for `insight`, it loads `InsightDraftRepository.get_active_draft(...)`.
7. The service builds a local audio path through `StoragePathPolicy.audio_path(...)` using current year, challenge week, a safe team slug, participant id, and a generated local file name.
8. The service calls `TelegramFileDownloader.download_file(...)` to save the Telegram file to the local path.
9. The service calls `SpeechTranscriber.transcribe(...)`.
10. Repository voice append operation stores one `draft_attachments` row and one ordered `draft_messages` row with `message_type = 'voice_transcription'`.
11. The service replies with `Голосовое принято и расшифровано.`
12. Existing weekly report or insight finalization assembles draft messages in order and writes the final Google Sheets row.
13. On download, local write, or transcription failure, the service records failed technical attachment state when possible, sends a technical notification through `NotificationRouter`, returns retry/text fallback copy, and does not clear the draft.

### Shared resources

| Resource | Owner (creates) | Consumers | Instance count |
|----------|-----------------|-----------|----------------|
| SQLite database path | application composition / tests | `DialogStateRepository`, weekly report draft repository, insight draft repository | 1 path per runtime |
| `StoragePathPolicy` | application composition / tests | voice service, report generator, storage tests | 1 policy object per service graph |
| `TelegramFileDownloader` | application composition / tests | voice service | 1 downloader boundary per main bot service graph |
| `SpeechTranscriber` | application composition / tests | voice service | 1 transcriber boundary per service graph |
| `NotificationRouter` | application composition / tests | voice service, weekly report service, insight service | 1 router per service graph |

## Decisions

### Decision 1: Voice is an input capability, not a finalization owner
**Decision:** `VoiceMessageService` only appends transcribed voice fragments to active drafts. It does not write final weekly reports or insights to Google Sheets.
**Rationale:** Supports US-AC1, US-AC5, US-AC6, and US-AC10. Existing flow services already enforce consent, deadline, duplicate, selected-step, and insight-progress isolation rules.
**Alternatives considered:** Let the voice service save final reports directly. Rejected because it would duplicate critical business rules and risk bypassing deadline or step-selection guards.

### Decision 2: Duration is checked before file download
**Decision:** Reject `duration_seconds > 600` before any download, local save, transcription, or draft mutation.
**Rationale:** Supports US-AC2 and the approved 10-minute MVP limit while minimizing storage and transcription cost.
**Alternatives considered:** Download first and inspect local media metadata. Rejected for MVP because Telegram voice metadata is sufficient for the current boundary tests and avoids unnecessary local files.

### Decision 3: Store attachment and transcription together in technical draft state
**Decision:** Each accepted voice creates a `draft_attachments` row and an ordered `draft_messages` row with the transcription text.
**Rationale:** Supports US-AC3, US-AC4, and US-AC7. Attachment metadata preserves audio file path and transcription status, while draft messages preserve text/voice ordering for final assembled text.
**Alternatives considered:** Store only transcription in `draft_messages`. Rejected because final Sheets rows need `audio_file_path`, and failures need technical attachment state.

### Decision 4: Keep audio local and non-public
**Decision:** All audio paths are built through `StoragePathPolicy.audio_path(...)`; no URL or user-provided multi-part path is accepted.
**Rationale:** Supports US-AC3, US-AC11, and the project storage boundary.
**Alternatives considered:** Store Telegram file ids or public links as long-term references. Rejected because approved docs require local VPS storage and no public audio links.

### Decision 5: Use fake boundaries in this feature
**Decision:** Add local protocols and fake implementations for Telegram file download and transcription tests; do not add live SDK dependencies.
**Rationale:** Supports US-AC13 and project testing patterns. Live credentials and post-deploy Telegram checks belong to deployment/smoke tasks, not this local feature slice.
**Alternatives considered:** Add `aiogram`/Telegram SDK and real transcription provider now. Rejected because current implementation slices avoid live SDK imports and secrets until explicit live integration work.

### Decision 6: Audio cleanup scheduler remains out of this implementation slice
**Decision:** This feature does not implement the final automatic deletion job for one-month audio retention.
**Rationale:** Supports US-AC12 by ensuring final data relies on transcription text and by preserving `audio_deleted_at` compatibility, but user-spec explicitly allows cleanup to be scoped by tech spec. The current slice focuses on receiving, storing, transcribing, and attaching audio.
**Alternatives considered:** Add `audio_cleanup` job now. Rejected to keep the feature M-sized and because scheduler execution is a separate MVP phase.

## Data Models

### New service models

Expected in `app/services/voice_messages.py`:

- `VoiceMessageInput`
  - `user: TelegramUserContext`
  - `telegram_file_id: str`
  - `duration_seconds: int`
  - `telegram_message_id: int | None`
  - `now: datetime`
- `StoredVoiceAttachment`
  - `local_file_path: Path`
  - `transcription_text: str`
  - `duration_seconds: int`

### Telegram file boundary

Expected in `app/bot/clients.py`:

- `TelegramFileDownload`
  - `telegram_file_id: str`
  - `destination_path: Path`
- `TelegramFileDownloader` protocol
  - `download_file(request: TelegramFileDownload) -> Path`
- `FakeTelegramFileDownloader`
  - creates deterministic local test files without live SDK imports.

### SQLite draft repositories

Extend `WeeklyReportDraftRepository` and `InsightDraftRepository` with voice append operations. The exact method names may vary during implementation, but each repository must support:

- loading active draft by `telegram_id`;
- appending a `draft_attachments` row with `telegram_file_id`, `local_file_path`, `duration_seconds`, `transcription_status`, optional `transcription_text`, and optional `error_message`;
- appending an ordered `draft_messages` row with `message_type = 'voice_transcription'`;
- touching `draft_sessions`, flow-specific draft table, and `dialog_states`.

No new SQLite tables are required. Existing `draft_attachments` and `draft_messages` schema already covers the technical state.

### Google Sheets final rows

No protocol-level new method is required if existing `append_weekly_report(...)` and `append_insight(...)` receive rows with:

- `transcription_text`
- `audio_file_path`
- `audio_deleted_at`

Weekly report and insight services must preserve these fields when finalizing drafts that contain voice attachments. If multiple voice messages exist, `transcription_text` may be the joined transcription text in draft order and `audio_file_path` may be a deterministic separator-joined list or the first path plus future-proof metadata, as long as tests document the chosen local convention. If this convention changes docs-level schema expectations, it must be recorded before approval.

## Dependencies

### New packages
- None.

### Using existing (from project)
- `app.bot.clients` — add Telegram file download boundary and fake implementation.
- `app.bot.messages` — approved Russian voice copy.
- `app.scheduler.calendar` — current challenge week/year and deadline context.
- `app.services.notifications` — admin-only technical error routing.
- `app.services.participant_models` — `TelegramUserContext` and `FlowResponse`.
- `app.speech.transcription` — `MAX_VOICE_DURATION_SECONDS`, `SpeechTranscriber`, fake transcriber.
- `app.storage.dialog_state` — active flow lookup.
- `app.storage.paths` — safe local audio path construction.
- `app.storage.weekly_report_drafts` — weekly draft append/read/clear.
- `app.storage.insight_drafts` — insight draft append/read/mark-saved cleanup.

## Testing Strategy

**Feature size:** M

### Unit tests
- Telegram file boundary fake writes only to requested local path and imports no live SDKs.
- Speech duration boundary still rejects duration greater than 600 seconds.
- `StoragePathPolicy.audio_path(...)` rejects public URLs, absolute paths, traversal fragments, and multi-part fragments.
- Voice copy constants match approved Russian text.

### Integration tests
- Weekly report draft repository appends text and voice transcription fragments in original order.
- Insight draft repository appends text and voice transcription fragments in original order.
- Draft repositories store accepted voice attachment metadata and failed transcription metadata without creating business-primary tables.
- `VoiceMessageService` rejects voice without active draft and does not download.
- `VoiceMessageService` rejects voice over 600 seconds and does not download, transcribe, or mutate draft.
- `VoiceMessageService` accepts weekly-report voice, downloads through fake boundary, transcribes through fake boundary, appends to draft, and final weekly report contains report text, transcription text, and audio path.
- `VoiceMessageService` accepts insight voice and final insight contains insight text, transcription text, and audio path without changing weekly progress.
- Download/save/transcription failure preserves active draft, sends admin-only technical error, and returns retry/text fallback copy.
- Existing weekly report deadline, duplicate, selected-step, and empty-content regressions still pass.
- Existing insight privacy cleanup still removes draft message text after save.

### E2E tests
- None in this feature. Live Telegram voice download and real transcription provider checks are deferred to later smoke/post-deploy verification with test bot, test Google Sheets, and protected credentials.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

The implementing agent verifies the feature locally with fake boundaries and temporary SQLite. No production bot, production Google Sheets, real audio provider, deploy, or push is required for this feature.

### Tools required

- bash / pytest
- Python standard library filesystem and SQLite
- No Playwright MCP, Telegram MCP, curl, deploy, or live external API call for this draft feature.

## Risks

| Risk | Mitigation |
|------|------------|
| Full transcription text remains in SQLite after final save | Keep final text in Google Sheets and clear active draft state after successful weekly/insight save; preserve insight saved-draft cleanup behavior. |
| Voice service bypasses weekly report business rules | Voice service only appends draft fragments; finalization remains in `WeeklyReportService`. |
| Audio path is unsafe or public | Use `StoragePathPolicy.audio_path(...)` and add regression tests for unsafe fragments. |
| Transcription failure loses user input | Do not clear draft on failure; send retry/text fallback copy and admin-only technical error. |
| Live SDKs or secrets leak into local tests | Use protocols and fakes only; update boundary import tests to reject live SDK imports in boundary modules. |
| Multiple voice messages create ambiguous final Sheets fields | Define and test one deterministic convention for joined transcription text and audio path fields during implementation. |

## User-Spec Deviations

None

## Acceptance Criteria

- [ ] `work/voice-processing/user-spec.md` status is approved before implementation tasks start.
- [ ] No live Telegram, Google, OpenAI/Whisper, or external transcription SDK is imported by boundary modules in this feature.
- [ ] Voice duration over 600 seconds is rejected before download/transcription/draft mutation.
- [ ] Accepted voice creates local non-public audio path through `StoragePathPolicy`.
- [ ] Accepted voice appends one technical attachment row and one ordered `voice_transcription` draft message.
- [ ] Mixed text and voice messages are assembled in original order for weekly reports and insights.
- [ ] Weekly report finalization includes transcription/audio fields and still enforces deadline, duplicate, selected-step, and empty-content guards.
- [ ] Insight finalization includes transcription/audio fields, does not affect weekly status/progress, and preserves post-save draft text cleanup.
- [ ] Voice processing failures preserve active draft and route technical details only to admin error chat.
- [ ] Full local pytest suite passes.
- [ ] No generated audio files, SQLite databases, credentials, or secrets are staged.

## Implementation Tasks

### Wave 1 (independent foundations)

#### Task 1: Voice message contracts and Telegram file boundary
- **Description:** Add adapter-independent voice input models, approved Russian copy constants, and a Telegram file download protocol with a fake implementation. This gives later tasks a live-SDK-free way to validate duration, download behavior, and user-facing responses.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_boundaries.py tests/test_weekly_report_messages.py tests/test_insight_messages.py -q` -> pass
- **Files to modify:** `app/bot/clients.py`, `app/bot/messages.py`, `app/services/voice_messages.py`, `tests/test_boundaries.py`, `tests/test_voice_processing_messages.py`
- **Files to read:** `app/speech/transcription.py`, `app/storage/paths.py`, `work/voice-processing/user-spec.md`

#### Task 2: Draft attachment repository operations
- **Description:** Extend weekly report and insight draft repositories so accepted voice messages can store attachment metadata and ordered transcription messages. This keeps voice state technical and temporary while preserving existing text draft behavior.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py tests/test_insight_draft_repository.py tests/test_sqlite_schema.py -q` -> pass
- **Files to modify:** `app/storage/weekly_report_drafts.py`, `app/storage/insight_drafts.py`, `tests/test_weekly_report_draft_repository.py`, `tests/test_insight_draft_repository.py`, `tests/test_sqlite_schema.py`
- **Files to read:** `app/storage/sqlite.py`, `app/storage/dialog_state.py`, `tests/test_weekly_report_finalize.py`, `tests/test_insight_add_flow.py`

### Wave 2 (depends on Wave 1)

#### Task 3: Voice processing service
- **Description:** Implement the shared voice service that routes voice input to the active weekly report or insight draft, validates duration before download, stores audio locally, transcribes it, and handles failures without clearing drafts. This centralizes voice-specific behavior while leaving final business writes in existing flow services.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_voice_processing_service.py -q` -> pass
- **Files to modify:** `app/services/voice_messages.py`, `tests/test_voice_processing_service.py`
- **Files to read:** `app/storage/dialog_state.py`, `app/storage/paths.py`, `app/services/notifications.py`, `app/speech/transcription.py`, `app/services/participant_models.py`

#### Task 4: Weekly report voice integration
- **Description:** Replace weekly report voice rejection with voice draft appending and ensure final weekly report rows include transcription/audio fields. This lets participant report voice input reuse existing deadline, duplicate, selected-step, and final save rules.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py tests/test_voice_processing_service.py -q` -> pass
- **Files to modify:** `app/services/weekly_reports.py`, `tests/test_weekly_report_finalize.py`, `tests/test_weekly_report_boundaries.py`
- **Files to read:** `app/services/weekly_report_models.py`, `app/sheets/gateway.py`, `app/storage/weekly_report_drafts.py`, `app/bot/messages.py`

#### Task 5: Insight voice integration
- **Description:** Replace insight voice rejection with voice draft appending and ensure final insight rows include transcription/audio fields without changing weekly progress. This keeps insights separate from weekly reports while supporting voice input and post-save privacy cleanup.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_insight_boundaries.py tests/test_voice_processing_service.py -q` -> pass
- **Files to modify:** `app/services/insights.py`, `tests/test_insight_add_flow.py`, `tests/test_insight_boundaries.py`
- **Files to read:** `app/services/insight_models.py`, `app/sheets/gateway.py`, `app/storage/insight_drafts.py`, `app/bot/messages.py`

### Wave 3 (cross-flow regressions)

#### Task 6: Voice boundary regression coverage
- **Description:** Add cross-flow regressions for mixed text/voice ordering, over-limit rejection, unsafe audio path rejection, failure notification routing, and no-secret/no-audio artifact staging assumptions. This protects the feature against privacy and business-rule regressions across weekly reports and insights.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_voice_processing_boundaries.py tests/test_boundaries.py tests/test_storage_paths.py -q` -> pass
- **Files to modify:** `tests/test_voice_processing_boundaries.py`, `tests/test_boundaries.py`, `tests/test_storage_paths.py`
- **Files to read:** `app/services/voice_messages.py`, `app/storage/paths.py`, `app/services/notifications.py`, `tests/test_participant_boundaries.py`

### Audit Wave

#### Task 7: Code Audit
- **Description:** Full-feature code quality audit for all voice-processing source and test changes. Review cross-component boundaries, shared resources, duplicate logic, and consistency with the approved architecture.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 8: Security Audit
- **Description:** Full-feature security audit for voice duration validation, file path safety, secret handling, personal transcription storage, role/consent boundaries, and admin-only technical error routing. Write a structured audit report.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 9: Test Audit
- **Description:** Full-feature test quality audit for voice-processing unit, integration, and boundary tests. Verify that assertions cover meaningful behavior and that no live secrets or external services are required.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 10: Pre-deploy QA
- **Description:** Run full local acceptance testing for voice-processing and verify all user-spec and tech-spec acceptance criteria with fake/local boundaries. Confirm no deploy, live Telegram, live Google Sheets, real transcription provider, generated audio, or secrets are required.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `.venv/bin/python -m pytest -q` -> pass
- **Files to modify:** `work/voice-processing/logs/working/task-10/pre-deploy-qa.json`, `work/voice-processing/tasks/10.md`, `work/voice-processing/decisions.md`
- **Files to read:** `work/voice-processing/user-spec.md`, `work/voice-processing/tech-spec.md`, `work/voice-processing/tasks/`, `work/voice-processing/logs/working/`
