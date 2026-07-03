---
created: 2026-07-01
status: approved
branch: main
size: L
---

# Tech Spec: mvp-foundation

## Solution

Build the first executable foundation for the Telegram Goals Bot MVP as a Python application with explicit module boundaries, configuration loading, SQLite technical-state schema, scheduler constants, file-storage paths, Google Sheets boundary interfaces, and notification routing boundaries for three Telegram bots.

This feature intentionally does not implement full participant/captain flows, voice transcription, final PDF generation, production deployment, or real Google Sheets writes. It creates the safe base those later features will use.

The implementation should make local verification possible without production secrets:

- configuration can be loaded and validated from environment variables or `.env`, while challenge timezone remains a fixed scheduler constant;
- secrets are redacted in logs and diagnostic output;
- SQLite schema can be initialized in a temporary database;
- scheduler calendar constants can be tested deterministically;
- Google Sheets and Telegram interactions are represented through boundaries/protocols/fakes, not live external calls;
- tests can run locally with no Telegram token and no Google credentials.

## Architecture

### What we're building/modifying

- **Python package and test tooling** — create project metadata, test command, package import structure, and minimal developer commands.
- **Configuration layer** — typed settings loader for env variables, `.env` support, validation, and secret redaction. Challenge timezone is not an env setting in MVP.
- **Logging layer** — shared logger setup that avoids leaking tokens and credential paths.
- **SQLite technical-state layer** — schema and initializer for dialog state, drafts, scheduler state, reminders, and technical errors.
- **Google Sheets boundary** — interfaces and fake implementation for future business-data reads/writes.
- **Telegram bot boundary** — explicit runtime distinction between main bot, error bot, and notification bot.
- **Notification routing boundary** — route categories that prevent technical errors from going to participants/captains/trackers/Sitnikov.
- **Scheduler foundation** — timezone, challenge calendar, reminder schedule, and idempotency-key helpers.
- **File storage foundation** — configured local paths and retention constants for audio, SQLite, PDFs, backups.
- **Documentation and smoke checks** — README/docs updates only for local foundation checks, not product behavior changes.

### How it works

Startup-level flow:

1. Config loader reads environment variables and optional `.env`.
2. Config validation fails clearly if required settings are missing for a selected runtime mode. Strict/runtime mode requires all three Telegram bot tokens.
3. Logging setup receives redacted config metadata only.
4. SQLite initializer creates technical-state tables in `SQLITE_DB_PATH`.
5. Boundary modules expose protocols/fakes for Sheets, Telegram bots, notifications, reports, speech, scheduler, and storage.
6. Local tests instantiate foundation components with fake settings and temporary SQLite paths.

Layering rules:

- `app.bot` may depend on `app.services` and boundary interfaces, but must not directly own Google Sheets or SQLite implementation details.
- `app.services` owns business-facing orchestration contracts, but this feature only creates boundaries/skeletons.
- `app.sheets` owns Google Sheets gateway interfaces/fakes.
- `app.storage` owns SQLite technical state and local file path policies.
- `app.scheduler` owns calendar constants, schedule definitions, and idempotency helpers.
- `app.reports` owns report-generation boundaries and PDF path policies.
- `app.speech` owns voice-processing boundaries and audio path policy.

### Shared resources

| Resource | Owner (creates) | Consumers | Instance count |
|----------|----------------|-----------|----------------|
| App settings | `app.config` | All layers | 1 per process |
| SQLite connection factory | `app.storage.sqlite` | Technical state repositories, scheduler state | Many short-lived connections or one injected connection in tests |
| Main bot client boundary | `app.bot.clients` | Participant/captain flows in later features | 1 configured boundary |
| Error bot client boundary | `app.bot.clients` | Error notification routing | 1 configured boundary |
| Notification bot client boundary | `app.bot.clients` | Operational notifications and reports | 1 configured boundary |
| Google Sheets gateway boundary | `app.sheets.gateway` | Services and reports in later features | 1 configured gateway/fake per runtime |

## Decisions

### Decision 1: Python package and pytest foundation
**Decision:** Create a Python package structure with project metadata and `pytest` as the test runner.  
**Rationale:** Supports user-spec AC "В проекте есть тестовая база" and makes foundation verifiable before user flows exist.  
**Alternatives considered:** Keep loose scripts only. Rejected because the MVP needs multiple long-lived modules and testable boundaries.

### Decision 2: Typed settings with `.env` support
**Decision:** Use typed settings loading with explicit required variables and secret redaction. Strict/runtime mode requires main, error, and notification bot tokens from the start.  
**Rationale:** Supports user-spec AC for env-based config, three Telegram bot tokens, and no secrets in logs.  
**Alternatives considered:** Read `os.environ` ad hoc in each module. Rejected because it spreads validation and makes secret handling inconsistent.

### Decision 3: SQLite as technical-state schema only
**Decision:** Implement SQLite schema only for dialog/draft/scheduler/reminder/error technical state.  
**Rationale:** Supports user-spec constraints that Google Sheets remains business source of truth and SQLite must not become business storage.  
**Alternatives considered:** Add participant/goal/report business tables to SQLite. Rejected because it violates approved product decisions.

### Decision 4: Boundary-first external integrations
**Decision:** Represent Telegram bots and Google Sheets through boundaries/fakes in foundation; defer live API calls.  
**Rationale:** Supports user-spec requirement that unit/integration tests do not need production credentials and that full flows come later.  
**Alternatives considered:** Install Telegram and Google API SDKs immediately. Rejected for foundation because no live integration flow is implemented yet.

### Decision 5: Three-bot model is structural
**Decision:** Model main bot, error bot, and notification bot as distinct config sections and routing categories from the start.  
**Rationale:** Supports final product decision and user-spec AC that notification routing distinguishes all three.  
**Alternatives considered:** One bot with message types. Rejected because user explicitly approved three separate bots.

### Decision 6: Scheduler calendar constants are executable, not only documented
**Decision:** Encode fixed `Asia/Yekaterinburg`, `2026-07-31`, 8 weeks + 4 final-summary days, and reminder times as tested constants/helpers. Do not allow runtime timezone override in MVP foundation.  
**Rationale:** Supports user-spec AC for scheduler foundation and prevents later date drift.  
**Alternatives considered:** Leave calendar only in docs until scheduler feature. Rejected because downstream features need stable shared constants.

### Decision 7: No deployment in foundation
**Decision:** Do not create production systemd units or deploy workflows in this feature.  
**Rationale:** Supports user-spec constraint "прямой deploy сейчас не делаем"; deployment will be a separate feature after app behavior exists.  
**Alternatives considered:** Add systemd service now. Rejected because there is not yet a runnable production bot.

## Data Models

### SQLite technical-state tables

Foundation creates the physical schema from `docs/05_sqlite_state_schema.md`. The document is the logical source of truth, but implementation must turn it into an explicit SQLite schema with primary keys, unique constraints, indexes, `CHECK` constraints for known technical values, and idempotency constraints.

- `draft_sessions`
- `dialog_states`
- `draft_messages`
- `draft_attachments`
- `draft_reports`
- `draft_insights`
- `scheduler_jobs`
- `job_runs`
- `reminder_log`
- `error_events`

The schema must not include business-primary tables for participants, teams, goals, planned steps, weekly reports, insights, or final report facts.

Key physical decisions:

- `draft_sessions` owns `draft_id` and draft lifecycle state.
- `dialog_states.telegram_id` is unique.
- `draft_messages` enforces unique message order per `draft_id`.
- `scheduler_jobs` prevents duplicate jobs for the same `job_type`, `week_number`, and `scheduled_for`.
- `job_runs.idempotency_key` is unique.
- `reminder_log` prevents duplicate reminders for the same `participant_id`, `week_number`, and `reminder_type`.
- Multi-step selections are stored as JSON text and validated in application code.

### Settings model

Settings groups:

- `TelegramSettings`: `MAIN_TELEGRAM_BOT_TOKEN`, `ERROR_TELEGRAM_BOT_TOKEN`, `NOTIFICATION_TELEGRAM_BOT_TOKEN`. All three are required in strict/runtime mode.
- `GoogleSheetsSettings`: `GOOGLE_SHEETS_ID`, `GOOGLE_APPLICATION_CREDENTIALS`.
- `AdminSettings`: admin, error chat, Sitnikov, tracker IDs.
- `StorageSettings`: `SQLITE_DB_PATH`, `AUDIO_STORAGE_DIR`, `PDF_STORAGE_DIR`, backup paths.
- `RuntimeSettings`: `LOG_LEVEL`, environment mode. Timezone is owned by scheduler constants, not runtime settings.

### Boundary interfaces

- Sheets gateway: future reads/writes for participants, goals, planned steps, reports, insights.
- Bot clients: future message sending for main/error/notification bots.
- Notification router: category-based dispatch with explicit recipient class.
- Report boundary: future PDF generation and local path creation.
- Speech boundary: future audio save/transcription hook.

## Dependencies

### New packages

- `pytest` — automated tests.
- `python-dotenv` — local `.env` loading without requiring production environment injection.

Use only Python standard library for SQLite, logging, dataclasses/typing, filesystem paths, and timezone handling where practical.

Do not add Telegram SDK, Google API SDK, PDF library, speech/transcription SDK, Docker tooling, Redis, Celery, PostgreSQL driver, or Kubernetes tooling in this foundation feature.

### Using existing (from project)

- `docs/01_requirements.md` — business requirements.
- `docs/02_open_questions.md` — resolved product decisions.
- `docs/03_architecture.md` — module boundaries.
- `docs/04_google_sheets_schema.md` — Sheets boundary shape.
- `docs/05_sqlite_state_schema.md` — SQLite technical schema.
- `docs/08_mvp_plan.md` — MVP implementation sequencing.
- `.env.example` — approved configuration names.
- `app/` — existing empty package directories to populate.
- `tests/` — existing empty test directory.

## Testing Strategy

**Feature size:** L

### Unit tests
- Settings validation succeeds with complete fake env.
- Settings validation fails clearly with missing required env for runtime mode.
- Settings validation fails if any one of the three Telegram bot tokens is missing in strict/runtime mode.
- Secret redaction hides bot tokens and credential-like values.
- Scheduler constants expose fixed timezone, challenge end date, and reminder times.
- File path policy builds expected audio/PDF/backup paths without public URLs.
- Notification categories map technical errors only to error bot boundary.

### Integration tests
- SQLite schema initializes in a temporary database.
- SQLite schema contains required technical-state tables.
- SQLite schema exposes required primary keys, unique constraints, and indexes for draft/session/scheduler idempotency.
- SQLite schema does not create business-primary tables.
- Config + logging setup can run with fake settings without leaking tokens.
- Package imports across `app.*` layers work in a clean test process.

### E2E tests
- None for this feature. Complete Telegram user flows are out of scope and will get E2E tests in later flow-specific features.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Agent verifies foundation locally with tests and smoke commands. No production Telegram bot, Google Sheets access, or deployment is required.

### Tools required

- bash
- pytest
- python local commands

No Playwright MCP, Telegram MCP, live Google API call, or deployment tool is required for this feature.

## Risks

| Risk | Mitigation |
|------|-----------|
| Foundation grows into full MVP implementation | Keep tasks limited to package/config/schema/boundaries/tests. Defer user flows, live API calls, PDF generation, and deploy. |
| SQLite duplicates business data | Tests assert only technical-state tables are created. Tech spec forbids business-primary tables. |
| Three-bot model becomes confusing | Encode bot purpose in settings and routing categories; document boundary names clearly. |
| Scheduler date math drifts from product decisions | Constants/helpers covered by unit tests against `2026-07-31`, `Asia/Yekaterinburg`, and fixed reminder times. |
| Secrets leak through logs or test failures | Redaction helper and tests cover token-like fields. `.env` remains ignored. |

## User-Spec Deviations

None

## Acceptance Criteria

- [ ] Python project metadata and package imports work.
- [ ] `pytest` test suite exists and passes.
- [ ] Settings loader supports `.env` and required MVP env vars.
- [ ] Strict/runtime settings validation requires all three Telegram bot tokens.
- [ ] Settings/logging redacts secret values.
- [ ] SQLite schema initializer creates only technical-state tables.
- [ ] SQLite schema includes physical constraints for draft identity, scheduler idempotency, and reminder deduplication.
- [ ] Google Sheets gateway boundary exists with fake implementation for tests.
- [ ] Main/error/notification bot boundaries exist as separate concepts.
- [ ] Notification routing prevents technical errors from using participant/captain/tracker/Sitnikov routes.
- [ ] Scheduler constants match approved product decisions.
- [ ] File-storage policy matches audio, SQLite, PDF, and backup paths.
- [ ] No Docker, PostgreSQL, Redis, Celery, Kubernetes, live Telegram SDK, live Google API SDK, PDF library, or speech SDK is introduced.
- [ ] README or docs contain local foundation verification commands if needed.

## Implementation Tasks

### Wave 1 (independent)

#### Task 1: Python package and test tooling
- **Description:** Create Python project metadata, package initialization, and a reliable local test command. This enables all later foundation work to be verified consistently.
- **Skill:** infrastructure-setup
- **Reviewers:** infrastructure-reviewer, test-reviewer
- **Verify-smoke:** `python -m pytest` → tests are discovered and run
- **Files to modify:** `pyproject.toml`, `app/__init__.py`, `tests/`
- **Files to read:** `README.md`, `.gitignore`, `.env.example`

#### Task 2: Settings and secret redaction
- **Description:** Add typed configuration loading from environment and optional `.env`, including three Telegram bot tokens and storage paths. Add redaction so diagnostic output cannot leak tokens or credential-like values.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_config.py` → config and redaction tests pass
- **Files to modify:** `app/config.py`, `app/logging.py`, `tests/test_config.py`
- **Files to read:** `.env.example`, `docs/03_architecture.md`, `.claude/skills/project-knowledge/references/deployment.md`

### Wave 2 (depends on Wave 1)

#### Task 3: SQLite technical-state schema
- **Description:** Implement SQLite schema initialization for technical state only. The result must support dialog/draft/scheduler/reminder/error state and must not create business-primary storage.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_sqlite_schema.py` → schema tests pass against a temporary database
- **Files to modify:** `app/storage/sqlite.py`, `tests/test_sqlite_schema.py`
- **Files to read:** `docs/05_sqlite_state_schema.md`, `docs/04_google_sheets_schema.md`

#### Task 4: Scheduler and file-storage foundations
- **Description:** Add executable calendar constants, reminder schedule definitions, idempotency-key helpers, and local file path policies for audio, SQLite, PDFs, and backups. This gives later scheduler and report features a single source for approved dates and paths.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_scheduler_foundation.py tests/test_storage_paths.py` → scheduler and path policy tests pass
- **Files to modify:** `app/scheduler/calendar.py`, `app/storage/paths.py`, `tests/test_scheduler_foundation.py`, `tests/test_storage_paths.py`
- **Files to read:** `docs/02_open_questions.md`, `docs/03_architecture.md`, `docs/05_sqlite_state_schema.md`

### Wave 3 (depends on Wave 1)

#### Task 5: External integration boundaries
- **Description:** Create boundary interfaces and fake implementations for Google Sheets, Telegram bot clients, notification routing, report generation, and speech processing. This preserves module separation without requiring live external APIs in foundation.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_boundaries.py` → boundary tests pass without live credentials
- **Files to modify:** `app/sheets/gateway.py`, `app/bot/clients.py`, `app/services/notifications.py`, `app/reports/generator.py`, `app/speech/transcription.py`, `tests/test_boundaries.py`
- **Files to read:** `docs/03_architecture.md`, `docs/04_google_sheets_schema.md`, `docs/07_reports.md`

#### Task 6: Foundation documentation and smoke commands
- **Description:** Document local foundation verification commands and clarify that no production deploy or full user flow is included in this feature. This helps the user and future agents verify the base safely.
- **Skill:** documentation-writing
- **Reviewers:** documentation-reviewer
- **Verify-smoke:** `python -m pytest` → documented test command succeeds
- **Files to modify:** `README.md`, `docs/08_mvp_plan.md`
- **Files to read:** `work/mvp-foundation/user-spec.md`, `docs/08_mvp_plan.md`

### Audit Wave

#### Task 7: Code Audit
- **Description:** Full-feature code quality audit. Read all source files created/modified in this feature and review module boundaries, duplicate initialization risks, and consistency with the architecture decisions.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 8: Security Audit
- **Description:** Full-feature security audit. Review settings, logging, SQLite schema, and routing boundaries for secret leakage, unsafe file paths, and unauthorized notification routes.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 9: Test Audit
- **Description:** Full-feature test quality audit. Verify that tests meaningfully cover config, redaction, SQLite schema, scheduler constants, storage paths, and boundary behavior.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 10: Pre-deploy QA
- **Description:** Acceptance testing for foundation: run the full local test suite and verify user-spec and tech-spec acceptance criteria. No production deployment is performed for this feature.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `python -m pytest` → all tests pass
- **Files to read:** `work/mvp-foundation/user-spec.md`, `work/mvp-foundation/tech-spec.md`, `README.md`
