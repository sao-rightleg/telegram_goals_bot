---
created: 2026-07-10
status: approved
branch: dev
size: L
---

# Tech Spec: live-runtime-integration

## Solution

Build a test-live runtime layer around the already implemented MVP business services.

The feature adds concrete adapters for Telegram Bot API polling/sending/file download, Google Sheets business storage, and Yandex SpeechKit async transcription. It also adds runtime composition that wires these adapters to existing services and SQLite repositories, extends readiness checks, and adds a separate GitHub CI/CD deployment path for the test VPS environment.

This feature does not change the participant, weekly report, insight, voice, captain, scheduler, report, consent, deadline, progress, or role business rules. Existing services stay the source of business behavior; the new runtime layer only translates live external events into existing service method calls and sends returned responses through the existing bot boundaries.

Production launch remains out of scope. The deployable target for this feature is a separate test-live environment with separate GitHub environment/secrets, app directory, env file, systemd service, Telegram bot tokens, Google Sheet, and Yandex credentials.

## Architecture

### What we're building/modifying

- **Runtime composition** — creates live clients, repositories, notification router, storage path policy, and business services from `Settings`.
- **Telegram Bot API adapter** — implements `BotClient` for main/error/notification bots, implements `TelegramFileDownloader`, and provides a polling loop for the main bot.
- **Telegram update dispatcher** — maps Telegram commands, text messages, callback data, and voice messages into existing participant, weekly report, insight, and captain services.
- **Google Sheets adapter** — implements the existing `SheetsGateway` protocol using Google Sheets API v4 and validates required tabs/columns fail-fast.
- **Yandex SpeechKit adapter** — implements the existing synchronous `SpeechTranscriber` protocol by starting Yandex async recognition and polling with a bounded timeout.
- **Readiness checks** — extend `check-config`/startup to validate live env, local storage, Google credentials path, Google Sheets accessibility/schema, and provider selection.
- **Test deployment pipeline** — adds a separate GitHub Actions workflow and systemd unit template for `/opt/telegram_goals_bot_test` and `telegram-goals-bot-test.service`.

### How it works

1. `telegram-goals-bot --env-file ... check-config` loads strict settings, initializes storage, validates provider-specific config, creates live adapters in readiness mode, and validates the required Google Sheets schema.
2. `telegram-goals-bot --env-file ... run` loads the same settings, initializes storage, composes repositories/services/adapters, validates startup readiness, and starts Telegram long polling for the main bot.
3. The polling adapter receives Telegram updates and converts them into small internal update DTOs. It acknowledges updates by advancing the Telegram offset only after dispatch finishes or after a handled/sanitized failure is reported.
4. The dispatcher identifies the Telegram user context (`telegram_id`, `chat_id`, optional username), routes `/start`, consent callbacks, menu callbacks, weekly report callbacks, insight callbacks, captain callbacks, text messages, and voice messages to existing services.
5. Existing services write final business facts through `SheetsGateway`, technical state through SQLite repositories, voice files through `StoragePathPolicy`, and errors through `NotificationRouter`.
6. Technical errors are sanitized and routed only through the error bot to `ADMIN_ERROR_CHAT_ID`.
7. Voice handling downloads the Telegram voice file to the approved local audio path, calls the Yandex adapter through `SpeechTranscriber`, and appends only successful transcriptions to active weekly-report or insight drafts. Failed downloaded audio is deleted by the existing voice service behavior.
8. The test deploy workflow installs the same source package on the test VPS app directory, runs tests, runs `check-config` against the test env file, switches the test `current` symlink, and restarts only the test systemd service.

### Shared resources

| Resource | Owner (creates) | Consumers | Instance count |
|----------|-----------------|-----------|----------------|
| SQLite database file | `initialize_runtime()` / runtime composition | Dialog, draft, scheduler, report repositories | 1 file per environment |
| Telegram HTTP clients | Telegram adapter factory | Main/error/notification bot clients, file downloader, polling loop | 3 token-scoped clients plus downloader access |
| Google Sheets service client | Google Sheets adapter factory | `SheetsGateway` implementation and schema validator | 1 per process |
| Yandex SpeechKit HTTP client | Yandex transcriber factory | `SpeechTranscriber` implementation | 1 per process |
| Storage path policy | Runtime composition | Voice service, report/PDF services | 1 per process |

## Decisions

### Decision 1: Use direct HTTP adapters for Telegram and Yandex

**Decision:** Implement Telegram Bot API and Yandex SpeechKit adapters with a small HTTP client layer instead of adding a full Telegram framework or background job system.

**Rationale:** Supports user-spec constraints: Telegram-only MVP, no Redis/Celery/Docker, first test-live runtime, and bounded synchronous Yandex wait. Existing business services already provide the flow logic, so a framework would mostly add routing indirection.

**Alternatives considered:** `aiogram` for Telegram handlers was considered but rejected for this feature because existing services need explicit dispatcher mapping and the MVP does not need framework-specific state storage. A job queue for Yandex was considered but rejected for the first test smoke because the user-spec explicitly accepts a bounded wait inside the first provider implementation.

### Decision 2: Keep existing service boundaries as the runtime contract

**Decision:** The dispatcher calls existing `ParticipantFlowService`, `WeeklyReportService`, `InsightService`, `CaptainService`, and `VoiceMessageService` methods. It does not duplicate business rules in handler code.

**Rationale:** Supports user-spec requirements for preserving existing participant, weekly report, insight, voice, captain, scheduler, and report business rules.

**Alternatives considered:** Rebuilding flows in Telegram handlers was rejected because it would fork rules already covered by tests and increase the risk of role/deadline regressions.

### Decision 3: Validate Google Sheets schema before user flows

**Decision:** `check-config` and runtime startup validate all tabs and required columns used by the current `SheetsGateway` methods. Missing required tabs/columns fail startup; extra columns are allowed.

**Rationale:** Supports user-spec AC for fail-fast Google Sheets schema validation and manual admin-friendly extra columns.

**Alternatives considered:** Lazy validation per service call was rejected because it would let configuration errors appear during user interactions and make first live smoke harder to diagnose.

### Decision 4: Add provider-specific transcription settings while preserving `SpeechTranscriber`

**Decision:** Add typed settings for `TRANSCRIPTION_PROVIDER=yandex`, Yandex API key/IAM token or service-account credential path, folder id, operation timeout, and poll interval. Runtime composition selects the Yandex adapter behind the existing `SpeechTranscriber` protocol.

**Rationale:** Supports user-spec requirements for Yandex SpeechKit async as the first concrete provider and future provider abstraction.

**Alternatives considered:** Replacing the protocol with async methods was rejected for this feature because it would force broad changes in existing voice services.

### Decision 5: Use a separate test deploy workflow and systemd unit

**Decision:** Add test-specific deploy artifacts instead of parameterizing the production workflow at runtime.

**Rationale:** Supports user-spec requirements that test-live uses a separate GitHub environment, app dir, service, env file, tokens, sheet, and secrets, and that production remains blocked.

**Alternatives considered:** Reusing `deploy-production.yml` with different inputs was rejected because it increases the chance of mixing production/test service names and secrets.

### Decision 6: Acknowledge Telegram polling offsets only after handled dispatch

**Decision:** The polling loop advances update offset after dispatch returns or after the runtime catches the error, sends a sanitized admin error, and returns a safe user response when applicable.

**Rationale:** Supports user-spec risks around invalid state recovery and admin errors without creating infinite reprocessing for non-recoverable malformed updates.

**Alternatives considered:** Advancing offsets before dispatch was rejected because it could silently lose updates during transient failures. Never advancing on errors was rejected because one malformed update could block the whole polling stream.

### Decision 7: Do not include scheduler/report/PDF live smoke in this feature's first deploy gate

**Decision:** Runtime composition should not break scheduler/report services, but the post-deploy smoke for this feature focuses on interactive, voice, and captain flows. Scheduler/reports/PDF live checks remain a later pre-production stage.

**Rationale:** Supports user-spec stepwise smoke plan: minimal interactive flows first, then voice, then captain flow, broader scheduler/reports/PDF checks later.

**Alternatives considered:** Including full scheduler/report live smoke now was rejected because it expands the first live-runtime feature beyond the approved smoke scope.

## Data Models

### Settings additions

Extend `app.config.Settings` with typed sections while preserving current required settings:

- `TranscriptionSettings`
  - `provider: str`
  - `api_key: str | None`
  - `yandex_folder_id: str | None`
  - `yandex_iam_token: str | None`
  - `yandex_service_account_key_path: Path | None`
  - `operation_timeout_seconds: int`
  - `poll_interval_seconds: float`
- `TelegramRuntimeSettings`
  - `poll_timeout_seconds: int`
  - `poll_limit: int`
  - `request_timeout_seconds: int`

`.env.example` must include names only, never secret values.

### Telegram update DTOs

Add small internal DTOs in a runtime/telegram module:

- `TelegramUpdate`
  - `update_id`
  - `message`
  - `callback_query`
- `TelegramMessage`
  - `message_id`
  - `chat_id`
  - `telegram_id`
  - `username`
  - `text`
  - `voice_file_id`
  - `voice_duration_seconds`
- `TelegramCallback`
  - `callback_query_id`
  - `message_id`
  - `chat_id`
  - `telegram_id`
  - `username`
  - `data`

The DTOs are runtime translation objects only. They are not persisted as business data.

### Callback data

Use stable string prefixes that map to existing service methods:

- `consent:accept`
- `menu:view_goal`, `menu:view_steps`, `menu:view_progress`, `menu:view_insights`, `menu:view_team`, `menu:captain_manual_report`
- `weekly:start`, `weekly:status:{green|blue|red}`, `weekly:step:{step_id}`, `weekly:done`
- `insight:add`, `insight:list:{page}`, `insight:full:{insight_id}`, `insight:done`, `insight:skip_title`, `insight:cancel`
- `captain:participant:{participant_id}`, `captain:status:{green|blue|red}`, `captain:step:{step_id}`, `captain:done`

Callback parsing must reject malformed values safely and notify admin with sanitized technical context.

### Google Sheets schema registry

Add a registry that maps required tabs to columns based on `docs/04_google_sheets_schema.md` and current `SheetsGateway` usage:

- `Participants`
- `Teams`
- `Trackers`
- `Goals`
- `PlannedSteps`
- `WeeklyReports`
- `WeeklyReportSteps`
- `Insights`

The validator checks required headers only. Extra headers are allowed.

## Dependencies

### New packages

- `httpx` — Telegram Bot API and Yandex SpeechKit HTTP calls with timeouts.
- `google-api-python-client` — Google Sheets API v4 access.
- `google-auth` — Google service account credentials for Sheets.

### Using existing (from project)

- `app.runtime` — CLI entrypoint, runtime initialization, `run_bot()` blocker replacement.
- `app.config` — typed env loading and redaction.
- `app.bot.clients` — existing `BotClient` and `TelegramFileDownloader` protocols.
- `app.sheets.gateway` — existing `SheetsGateway` protocol.
- `app.speech.transcription` — existing `SpeechTranscriber` protocol and 600-second voice limit.
- `app.services.*` — existing business services for participant, weekly report, insight, voice, captain, notification routing.
- `app.storage.*` — existing SQLite repositories and storage paths.
- `.github/workflows/deploy-production.yml` — deployment pattern to copy into a test-specific workflow.
- `deploy/systemd/telegram-goals-bot.service` — production unit pattern to copy into a test-specific unit.

## Testing Strategy

**Feature size:** L

### Unit tests

- Telegram Bot API client maps send message/document/file download requests and sanitizes HTTP errors.
- Telegram update parser handles commands, text, callbacks, voice metadata, missing optional fields, and malformed updates.
- Dispatcher routes `/start`, consent, menu actions, weekly statuses/steps/done, insight actions, text messages, voice messages, and captain callbacks to the expected service calls.
- Invalid callback data and invalid dialog state produce safe user responses and sanitized admin errors.
- Google Sheets adapter maps row values to `SheetRow`, appends rows, updates participant consent, finds participants/goals/reports, and closes planned steps.
- Google Sheets schema validator fails on missing tabs/required columns and passes with extra columns.
- Yandex SpeechKit adapter submits audio, polls operation status, returns transcription text, handles timeout/failure/empty result, and never logs secret values.
- Settings validation selects `TRANSCRIPTION_PROVIDER=yandex` and rejects incomplete Yandex config.
- Runtime composition creates the expected concrete adapters/repositories/services.

### Integration tests

- `telegram-goals-bot --env-file ... check-config` passes with fake/live-like adapters and valid local config, and fails clearly for missing Google Sheets schema.
- `telegram-goals-bot --env-file ... run` can start in a controlled fake polling mode without `RuntimeNotImplementedError`.
- Full dispatcher integration with fake Sheets, fake Telegram API, fake transcriber, and temporary SQLite covers known participant `/start`, consent, menu, weekly report text save, insight text save, unknown user admin error, and captain own-team manual report.
- Voice integration with fake downloader/transcriber verifies successful draft append and failure cleanup/admin notification through the live runtime composition.
- Deployment workflow tests or static checks verify the test workflow references the test GitHub environment, test app dir secret, and test service name variables rather than production names.

### E2E tests

- Manual test-live smoke on VPS after GitHub CI/CD deploy:
  - known participant `/start`, consent, role menu, goal, planned steps, progress;
  - unknown Telegram account gets approved rejection text and admin error chat receives sanitized event;
  - weekly report text can be submitted to the test Google Sheet;
  - insight text can be submitted separately;
  - Russian voice under 10 minutes is transcribed by Yandex and added to active weekly-report or insight draft;
  - captain sees only own team and can submit one manual report for an own-team participant.

Scheduler, reports, PDF, and production smoke remain a later pre-production verification phase.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Implementation agents verify local behavior with unit/integration tests and fake/live-like adapters first. Live API credentials are not stored in the repository and are not required for automated tests. After code and test deployment artifacts are ready, deployment and post-deploy verification happen only after explicit user approval for the test-live deploy.

### Tools required

- `bash` / local CLI commands for pytest, config checks, package import checks, workflow/static checks.
- GitHub Actions for test-live deployment.
- Telegram manual smoke with test bot accounts.
- Google Sheets manual inspection for the test sheet.
- Yandex SpeechKit test credential only in secure env files/GitHub secrets, never in chat or repo.

## Risks

| Risk | Mitigation |
|------|------------|
| Test/prod secret or service mixing | Separate test workflow, GitHub environment, app dir, env file, service name, and systemd unit; production workflow unchanged and production deploy still requires separate approval. |
| Telegram callback state mismatch | Dispatcher tests for each callback family, safe malformed callback handling, invalid-state recovery via existing service methods/admin errors. |
| Google Sheets schema drift | Fail-fast required tab/header validation in `check-config` and startup; extra columns allowed. |
| Yandex async latency blocks bot responsiveness | Bounded timeout/poll interval settings; failure response asks user to retry/text; failed audio cleanup remains in existing voice service. |
| Secret or personal text leakage | Reuse redaction helpers, sanitize adapter/runtime errors, avoid report/voice/transcription text in admin technical errors. |
| Over-expanding into production launch | Tech-spec and tasks limit deploy to test-live; production launch remains separate approval after smoke. |
| Dependency creep | Add only HTTP and Google API packages; no Docker, Redis, Celery, PostgreSQL, web admin, or Telegram framework. |

## User-Spec Deviations

None

## Acceptance Criteria

- [ ] `telegram-goals-bot run` no longer raises `RuntimeNotImplementedError` when started with a valid test-live configuration.
- [ ] Runtime composition wires live Telegram, Google Sheets, Yandex SpeechKit, SQLite repositories, storage paths, notification router, and existing business services.
- [ ] Real Telegram bot clients implement `BotClient.send_message()` and `BotClient.send_document()` for main/error/notification bot purposes.
- [ ] Real Telegram file downloader implements `TelegramFileDownloader.download_file()` and stores voice files at the requested local path.
- [ ] Telegram polling loop receives main bot updates and dispatches `/start`, consent, menu, weekly report, insight, voice, and captain smoke actions.
- [ ] Real Google Sheets adapter implements all current `SheetsGateway` protocol methods used by smoke flows.
- [ ] Google Sheets schema validation fails startup/readiness for missing required tabs or columns and allows extra columns.
- [ ] Yandex SpeechKit async adapter implements `SpeechTranscriber` and is selected by `TRANSCRIPTION_PROVIDER=yandex`.
- [ ] Voice timeout/failure preserves existing drafts, deletes only failed just-downloaded audio, returns approved failure text, and sends sanitized admin error.
- [ ] Runtime/admin logs do not expose bot tokens, Yandex credentials, Google credentials, raw API keys, full report text, audio contents, or PDF contents.
- [ ] Test deployment workflow uses a separate GitHub `test` environment and test VPS target variables, and does not restart production service.
- [ ] Test systemd unit targets `/opt/telegram_goals_bot_test/current` and `telegram-goals-bot-test.service`.
- [ ] Automated tests pass locally with fake/live-like dependencies and no real secrets.
- [ ] Production deploy remains blocked until separate explicit approval after test-live smoke.

## Implementation Tasks

### Wave 1 (independent)

#### Task 1: Runtime configuration and provider selection
- **Description:** Extend typed settings for Telegram runtime options and Yandex transcription provider config. Result: config validation can distinguish valid test-live Yandex setup from missing/incomplete provider settings without exposing secrets.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_config.py tests/test_runtime_entrypoint.py -v`
- **Files to modify:** `app/config.py`, `.env.example`, `tests/test_config.py`, `tests/test_runtime_entrypoint.py`
- **Files to read:** `work/live-runtime-integration/user-spec.md`, `app/runtime.py`, `app/speech/transcription.py`

#### Task 2: Live Telegram Bot API clients
- **Description:** Implement concrete Telegram Bot API clients for sending messages/documents and downloading files behind existing bot boundaries. Result: main, error, and notification bot clients share behavior while remaining token-separated by purpose.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_boundaries.py -v`
- **Files to modify:** `app/bot/clients.py`, `tests/test_boundaries.py`
- **Files to read:** `app/services/notifications.py`, `app/storage/paths.py`

#### Task 3: Google Sheets adapter and schema validation
- **Description:** Implement a concrete `SheetsGateway` for Google Sheets API v4 and a fail-fast required schema validator. Result: existing services can read/write the test Google Sheet through the current protocol and readiness fails before user flows when required tabs/columns are missing.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py tests/test_insight_sheets_gateway.py tests/test_reports_sheets_gateway.py -v`
- **Files to modify:** `app/sheets/gateway.py`, `tests/test_participant_sheets_gateway.py`, `tests/test_weekly_report_sheets_gateway.py`, `tests/test_insight_sheets_gateway.py`, `tests/test_reports_sheets_gateway.py`
- **Files to read:** `docs/04_google_sheets_schema.md`, `app/services/participant_flows.py`, `app/services/weekly_reports.py`, `app/services/insights.py`, `app/services/captains.py`

#### Task 4: Yandex SpeechKit transcriber
- **Description:** Implement Yandex SpeechKit async recognition behind the existing `SpeechTranscriber` protocol. Result: voice processing can use `TRANSCRIPTION_PROVIDER=yandex` with bounded polling, clear failures, and no changes to existing draft/finalization rules.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_voice_processing_service.py tests/test_voice_processing_boundaries.py -v`
- **Files to modify:** `app/speech/transcription.py`, `tests/test_voice_processing_service.py`, `tests/test_voice_processing_boundaries.py`
- **Files to read:** `app/services/voice_messages.py`, `app/config.py`

### Wave 2 (depends on Wave 1)

#### Task 5: Telegram update parsing and dispatcher
- **Description:** Add runtime-level Telegram update parsing and route commands, callbacks, text, and voice into existing services. Result: the first interactive smoke flows can run from real Telegram updates without moving business rules into handlers.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_participant_start_flow.py tests/test_weekly_report_start_flow.py tests/test_insight_add_flow.py tests/test_captain_team_flow.py tests/test_captain_manual_report_flow.py -v`
- **Files to modify:** `app/runtime.py`, `app/bot/menus.py`, `tests/test_runtime_entrypoint.py`
- **Files to read:** `app/services/participant_flows.py`, `app/services/weekly_reports.py`, `app/services/insights.py`, `app/services/captains.py`, `app/services/voice_messages.py`, `app/storage/dialog_state.py`

#### Task 6: Runtime composition and readiness
- **Description:** Replace the not-implemented runtime path with composition of live adapters, SQLite repositories, notification router, storage path policy, and services. Result: `check-config` validates live readiness and `run` starts a controlled polling runtime for test-live without `RuntimeNotImplementedError`.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v`
- **Files to modify:** `app/runtime.py`, `tests/test_runtime_entrypoint.py`, `tests/test_project_tooling.py`
- **Files to read:** `app/config.py`, `app/storage/sqlite.py`, `app/services/notifications.py`, `app/storage/weekly_report_drafts.py`, `app/storage/insight_drafts.py`, `app/storage/dialog_state.py`

### Wave 3 (depends on Wave 2)

#### Task 7: Test-live deployment pipeline
- **Description:** Add separate test-live CI/CD and systemd artifacts for deploying to the VPS test environment. Result: GitHub Actions can deploy the test runtime without using production environment, production app dir, production service, or production secrets.
- **Skill:** deploy-pipeline
- **Reviewers:** code-reviewer, security-auditor, deploy-reviewer
- **Verify-smoke:** `python -m pytest tests/test_project_tooling.py -v`
- **Files to modify:** `.github/workflows/deploy-test.yml`, `deploy/systemd/telegram-goals-bot-test.service`, `docs/09_deployment_preparation.md`, `tests/test_project_tooling.py`
- **Files to read:** `.github/workflows/deploy-production.yml`, `deploy/systemd/telegram-goals-bot.service`, `.codex/skills/project-knowledge/references/deployment.md`

### Audit Wave

#### Task 8: Code Audit
- **Description:** Review all feature code holistically for architecture consistency, boundary use, unnecessary duplication, runtime lifecycle issues, and integration regressions. Result: an audit report with blocking findings or explicit OK.
- **Skill:** code-reviewing
- **Reviewers:** none
- **Files to modify:** `work/live-runtime-integration/logs/working/code-audit.json`
- **Files to read:** `app/config.py`, `app/runtime.py`, `app/bot/clients.py`, `app/sheets/gateway.py`, `app/speech/transcription.py`, `.github/workflows/deploy-test.yml`, `deploy/systemd/telegram-goals-bot-test.service`

#### Task 9: Security Audit
- **Description:** Review the full feature for secret handling, token redaction, Google/Yandex credential safety, Telegram role boundaries, personal data exposure, and CI/CD environment isolation. Result: a security audit report with blocking findings or explicit OK.
- **Skill:** security-auditor
- **Reviewers:** none
- **Files to modify:** `work/live-runtime-integration/logs/working/security-audit.json`
- **Files to read:** `app/config.py`, `app/logging.py`, `app/runtime.py`, `app/bot/clients.py`, `app/sheets/gateway.py`, `app/speech/transcription.py`, `.github/workflows/deploy-test.yml`

#### Task 10: Test Audit
- **Description:** Review feature tests for meaningful assertions, coverage of failure paths, fake/live boundary balance, and L-feature acceptance risk. Result: a test audit report with coverage gaps or explicit OK.
- **Skill:** test-master
- **Reviewers:** none
- **Files to modify:** `work/live-runtime-integration/logs/working/test-audit.json`
- **Files to read:** `tests/test_runtime_entrypoint.py`, `tests/test_boundaries.py`, `tests/test_voice_processing_service.py`, `tests/test_project_tooling.py`, `tests/test_*sheets_gateway.py`

### Final Wave

#### Task 11: Pre-deploy QA
- **Description:** Run acceptance testing before any test-live deploy. Result: all automated tests pass and acceptance criteria from user-spec and tech-spec are checked or explicitly deferred to post-deploy live smoke.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `python -m pytest -v`
- **Files to modify:** `work/live-runtime-integration/logs/working/pre-deploy-qa.md`
- **Files to read:** `work/live-runtime-integration/user-spec.md`, `work/live-runtime-integration/tech-spec.md`

#### Task 12: Deploy test-live
- **Description:** Deploy the approved feature to the separate test VPS environment through GitHub CI/CD after explicit user approval. Result: test service is installed/restarted while production service and production secrets remain untouched.
- **Skill:** deploy-pipeline
- **Reviewers:** none
- **Verify-user:** approve and run the GitHub `Deploy Test` workflow for the selected ref.
- **Files to modify:** `work/live-runtime-integration/logs/working/deploy-test.md`
- **Files to read:** `.github/workflows/deploy-test.yml`, `deploy/systemd/telegram-goals-bot-test.service`

#### Task 13: Post-deploy test-live verification
- **Description:** Verify the live test environment with real test bots, test Google Sheet, and Yandex SpeechKit. Result: interactive, voice, and captain smoke outcomes are recorded and production remains blocked until a later explicit approval.
- **Skill:** post-deploy-qa
- **Reviewers:** none
- **Verify-user:** run Telegram smoke with test accounts: `/start`, consent, menu, goal, steps, progress, weekly report text, insight text, one voice, captain own-team/manual report.
- **Files to modify:** `work/live-runtime-integration/logs/working/post-deploy-qa.md`
- **Files to read:** `work/live-runtime-integration/user-spec.md`, `work/live-runtime-integration/tech-spec.md`, `docs/09_deployment_preparation.md`
