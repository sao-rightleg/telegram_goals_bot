---
created: 2026-07-02
status: approved
branch: main
size: M
---

# Tech Spec: weekly-report-flow

## Summary

Implement an adapter-independent participant weekly report service for text reports. The feature starts a weekly report draft, validates participant identity and consent, enforces the current week deadline in `Asia/Yekaterinburg`, prevents duplicates, collects ordered text messages in SQLite technical draft state, and saves final `WeeklyReports` plus optional `WeeklyReportSteps` facts through the Google Sheets boundary.

This spec intentionally excludes live Telegram SDK wiring, live Google API adapter work, scheduler reminders, automatic gray no-answer closure, voice transcription, insights, captain manual reports, PDF generation, deploy, and production actions.

## User-Spec Requirements Mapping

| ID | Requirement |
|----|-------------|
| US-1 | Weekly report starts from a service-level entry point, not live Telegram wiring. |
| US-2 | Participant is identified by Telegram ID through the Google Sheets boundary. |
| US-3 | Unknown or non-consenting users cannot continue the flow. |
| US-4 | Current week and deadline use `Asia/Yekaterinburg`; late reports after Sunday 23:59 cannot change status. |
| US-5 | Duplicate reports for the same participant/week are rejected. |
| US-6 | Missing active goal or planned steps is handled safely and notifies admin without secrets. |
| US-7 | Start flow shows remaining open planned steps and green/blue/red status buttons. |
| US-8 | Green report requires selected open planned steps, saves green/🟩/1, closes relations and selected planned steps, and does not auto-achieve the final goal. |
| US-9 | Blue report requires selected planned steps, saves blue/🟦/0.5, creates partial relations, and does not close planned steps. |
| US-10 | Red report does not require selected steps, saves red/🟥/0, and does not close planned steps. |
| US-11 | Ordered text draft messages are stored in SQLite and assembled into final `report_text`. |
| US-12 | Voice messages are rejected with a short not-yet-available response. |
| US-13 | Finalize without report text does not create a WeeklyReport. |
| US-14 | Invalid or stale SQLite draft state is recovered safely and notifies admin. |
| US-15 | Final business facts are written only through Google Sheets; SQLite stores only technical draft/dialog state. |
| US-16 | Unit/integration tests pass without production Telegram tokens or Google credentials. |

## Architecture

### Components

#### Weekly report models and message contracts

Add feature-specific domain models for report statuses, draft state snapshots, selected step references, and service responses. Russian user-facing copy should live in bot message helpers and remain short, matching existing tone.

Primary objects:

- `WeeklyReportStatus`: `green`, `blue`, `red` with symbol and score mapping.
- `WeeklyReportDraft`: technical draft metadata loaded from SQLite.
- `WeeklyReportFinalPayload`: final business row payload prepared for Sheets.
- `WeeklyReportServiceResponse`: text, buttons/menu items, and optional metadata for tests/future adapters.

#### Sheets gateway extension

Extend `SheetsGateway` and `FakeSheetsGateway` with write/read operations required by final weekly reports:

- find a participant report for a week to prevent duplicates;
- append `WeeklyReports`;
- append `WeeklyReportSteps` relations;
- update selected planned steps to `closed` for green reports;
- list weekly report step relations for tests.

All methods must scope operations by `participant_id`, `goal_id`, and `step_id` where applicable. The fake gateway remains an in-memory boundary for tests and must not expose live Google API behavior.

#### SQLite weekly report draft repository

Add a repository over the existing SQLite schema:

- `draft_sessions`;
- `dialog_states`;
- `draft_reports`;
- `draft_messages`.

The repository creates/updates draft sessions, stores selected status and selected step IDs, appends ordered text messages, reads active draft state, and clears technical state after successful save or unsafe recovery. It must not store final business facts beyond temporary draft metadata already present in the approved schema.

#### Weekly report calendar helper

Add a small helper near `app/scheduler/calendar.py` or in a feature-local service module to calculate:

- current challenge week number;
- weekly deadline at Sunday 23:59 in `Asia/Yekaterinburg`;
- whether a report-changing action is still allowed.

The helper must reuse `TIMEZONE_NAME = "Asia/Yekaterinburg"` and the approved challenge calendar constants. It must be deterministic in tests by accepting an explicit `now`.

#### Weekly report service

Add `WeeklyReportService` as the feature orchestrator. It depends on the Sheets gateway, draft repository, notification router, and optional bot client abstraction only through existing boundaries.

Service operations:

- `start_report(user, now)`;
- `select_status(user, status, now)`;
- `select_steps(user, step_ids, now)`;
- `add_text_message(user, text, now, telegram_message_id=None)`;
- `reject_voice_message(user, now)`;
- `finalize_report(user, now)`;
- `recover_invalid_draft(user, reason, now)`.

The service validates identity, consent, deadline, duplicate report, active goal, open planned steps, selected step ownership, selected status requirements, and non-empty report text before final save.

### Data Flow

1. Future adapter calls `start_report` with a `TelegramUserContext`.
2. Service resolves participant by Telegram ID through Sheets and blocks unknown/non-consenting users.
3. Service calculates current week and deadline in `Asia/Yekaterinburg`.
4. Service checks for an existing WeeklyReport for participant/week.
5. Service loads active goal and planned steps, filters remaining open steps, creates a SQLite draft, and returns status buttons.
6. Participant selects green/blue/red.
7. For green/blue, selected step IDs are validated against the participant active goal. Red can continue without selected steps.
8. Text messages are appended to SQLite in order.
9. Finalize validates non-empty text, creates one WeeklyReport row, creates WeeklyReportSteps rows for green/blue, closes planned steps only for green, clears SQLite draft state, and returns confirmation text.

### Shared Resources

None. The feature uses injected gateway/repository/router objects and temporary SQLite files in tests. No new DB pools, browser instances, ML models, external API clients, or long-lived workers are introduced.

## Data Contracts

### WeeklyReports row

Required fields prepared by the service:

- `weekly_report_id`;
- `participant_id`;
- `team_id`;
- `goal_id`;
- `week_number`;
- `status_code`;
- `status_symbol`;
- `score`;
- `report_text`;
- `submitted_at`;
- `submitted_by_id`;
- `submitted_by_role`;
- `flow_source`.

The fake gateway may accept extra future-compatible fields but tests must assert the required fields.

### WeeklyReportSteps row

Required fields:

- `weekly_report_step_id`;
- `weekly_report_id`;
- `participant_id`;
- `goal_id`;
- `step_id`;
- `week_number`;
- `relation_status`: `closed` for green, `partial` for blue;
- `created_at`.

No relations are required for red.

### PlannedSteps update

For green only, selected steps are updated through Sheets boundary:

- `step_status = "closed"`;
- `closed_week_number = week_number`;
- `closed_report_id = weekly_report_id`;
- `closed_at = submitted_at`.

For blue and red, planned step status is unchanged.

### SQLite draft state

The draft repository uses existing tables:

- `draft_sessions.draft_type = "weekly_report"`;
- `draft_reports.status_code/status_symbol/selected_step_ids`;
- `draft_messages.message_type = "text"`;
- `dialog_states.flow = "weekly_report"`.

Selected step IDs should be serialized deterministically, for example comma-separated after validation. Final `report_text` is assembled by `message_order`.

## Error Handling

- Unknown user: return the existing unknown-user text and send an admin technical notification.
- Consent missing: return the existing consent text and keep the user outside weekly report draft state.
- Missing active goal or planned steps: return neutral missing-data text and notify admin with participant ID, missing type, and timestamp only.
- Late report: return `Дедлайн недели уже прошёл. Отчёт не может изменить статус.` and do not create final facts.
- Duplicate report: return a short accepted-already message and do not create duplicate facts.
- Empty text on finalize: ask the user to send report text and keep the draft active.
- Invalid/stale draft: clear unsafe draft/dialog state, return safe recovery text, and notify admin without secrets or unnecessary personal data.
- Sheets write failure: do not clear draft as saved; mark or keep draft recoverable and notify admin.

## Security and Privacy

- No production Telegram token, Google credentials, or live Sheets ID are required for tests.
- Admin notifications must not include secrets or full report text unless a future approved support scenario requires it.
- Step selection must be scoped to the current participant and active goal to prevent cross-participant writes.
- Final report data must go only through Sheets gateway methods.
- SQLite may store temporary report draft text until finalization or recovery, then it must be cleared.
- Voice attachments and audio files are not created in this feature.

## Testing Strategy

Feature size: M.

### Unit tests

- Status mapping for green/blue/red symbols and scores.
- Russian message helpers for status prompts, empty text, voice not available, late report, duplicate report, and success confirmations.
- Deadline/current-week helper with explicit `now` values around Sunday 23:59 Yekaterinburg.
- Step selection validation for green, blue, red, wrong participant, wrong goal, closed step for green, and empty selection.
- Draft repository ordered message assembly and clear behavior.

### Integration tests

- Green flow: start, select status, select open steps, add multiple text messages, finalize; assert WeeklyReport green/🟩/1, closed relations, planned steps closed, goal not auto-achieved, draft cleared.
- Blue flow: assert WeeklyReport blue/🟦/0.5, partial relations, planned steps unchanged, draft cleared.
- Red flow: assert WeeklyReport red/🟥/0, no required selected steps, planned steps unchanged, draft cleared.
- Empty finalize: no WeeklyReport is created and draft remains active.
- Deadline guard: late flow/final save is rejected and creates no final facts.
- Duplicate guard: second report for participant/week is rejected.
- Missing data: active goal/planned steps absence returns safe text and sends technical notification.
- Invalid draft recovery: unsafe state is cleared, no final facts are written, notification is sent.

### Regression/static tests

- Full suite passes with `.venv/bin/python -m pytest -q`.
- No live Telegram SDK wiring, live Google API adapter, scheduler reminder, PDF, voice transcription, deploy, Docker, Redis, Celery, or production actions are added.
- SQLite business-boundary tests assert no final-only business table is introduced locally.

## Decisions

- Decision 1: Keep weekly report behavior service-level and adapter-independent. Supports US-1 and US-16.
- Decision 2: Resolve users only through Telegram ID via `SheetsGateway`. Supports US-2 and US-3.
- Decision 3: Enforce deadline and duplicate checks before final save, and re-check them during finalization. Supports US-4 and US-5.
- Decision 4: Store draft/session/text state in SQLite and final facts in Sheets boundary only. Supports US-11 and US-15.
- Decision 5: Extend the existing Sheets fake instead of adding a real Google adapter in this feature. Supports US-1, US-15, and US-16.
- Decision 6: Require selected planned steps for green/blue and validate ownership through participant and active goal. Supports US-8, US-9, and Risk 2 from user-spec.
- Decision 7: Close planned steps only for green and never auto-achieve the final goal. Supports US-8, US-9, US-10, and the final-goal rule in the user-spec.
- Decision 8: Reject voice messages with copy only and create no audio/transcription state. Supports US-12 and out-of-scope constraints.
- Decision 9: Treat invalid draft state as a recoverable technical error, not as a partial business save. Supports US-14 and US-15.
- Decision 10: Do not include deploy or post-deploy verification in this feature. Supports the user-spec exclusions and project deployment constraints.

## User-Spec Deviations

None.

## Implementation Tasks

### Wave 1: Boundaries and Contracts

#### Task 1: Weekly report message and status contracts

Description: Add feature-level status mapping and Russian message helpers for weekly report prompts, validation errors, voice rejection, and success confirmations. This gives later service code a stable copy and status contract without live Telegram wiring.

Skill: `code-writing`
Reviewers: `code-reviewing`, `test-master`
Files to read: `work/weekly-report-flow/user-spec.md`, `app/bot/messages.py`, `app/services/participant_models.py`, `.codex/skills/project-knowledge/references/ux-guidelines.md`
Files to modify: `app/bot/messages.py`, `app/services/weekly_report_models.py`, `tests/test_weekly_report_messages.py`

#### Task 2: Weekly report Sheets boundary

Description: Extend the Sheets protocol and fake gateway for duplicate report lookup, WeeklyReportSteps relations, planned step closure, and test-only relation listing. This keeps final weekly report facts inside the approved Google Sheets boundary.

Skill: `code-writing`
Reviewers: `code-reviewing`, `security-auditor`, `test-master`
Files to read: `app/sheets/gateway.py`, `tests/test_participant_sheets_gateway.py`, `.codex/skills/project-knowledge/references/architecture.md`
Files to modify: `app/sheets/gateway.py`, `tests/test_weekly_report_sheets_gateway.py`

#### Task 3: Weekly report draft repository

Description: Add a SQLite repository for weekly report draft sessions, selected status/steps, ordered text messages, active draft loading, and draft clearing. The repository uses existing technical-state tables and must not create final business storage.

Skill: `code-writing`
Reviewers: `code-reviewing`, `security-auditor`, `test-master`
Files to read: `app/storage/sqlite.py`, `app/storage/dialog_state.py`, `tests/test_dialog_state_repository.py`, `tests/test_sqlite_schema.py`
Files to modify: `app/storage/weekly_report_drafts.py`, `tests/test_weekly_report_draft_repository.py`

#### Task 4: Weekly report calendar helper

Description: Add deterministic current-week and deadline helpers for the weekly report service using the approved `Asia/Yekaterinburg` calendar. Tests cover boundary times around Sunday 23:59.

Skill: `code-writing`
Reviewers: `code-reviewing`, `test-master`
Files to read: `app/scheduler/calendar.py`, `tests/test_scheduler_foundation.py`, `.codex/skills/project-knowledge/references/architecture.md`
Files to modify: `app/scheduler/calendar.py`, `tests/test_weekly_report_calendar.py`

### Wave 2: Service Flow

#### Task 5: Start, status selection, and step selection service flow

Description: Add the weekly report service entry points for starting a draft, selecting status, and selecting planned steps. The service validates identity, consent, deadline, duplicate report, active goal, planned steps, and step ownership before allowing the flow to progress.

Skill: `code-writing`
Reviewers: `code-reviewing`, `security-auditor`, `test-master`
Files to read: `app/services/participant_flows.py`, `app/services/notifications.py`, `app/sheets/gateway.py`, `app/storage/weekly_report_drafts.py`
Files to modify: `app/services/weekly_reports.py`, `tests/test_weekly_report_start_flow.py`, `tests/test_weekly_report_step_selection.py`

#### Task 6: Text draft collection and final save

Description: Add text message collection, voice rejection, empty-text finalization guard, final WeeklyReport save, WeeklyReportSteps save, green planned-step closure, and draft cleanup. This task completes the business write path through the Sheets boundary.

Skill: `code-writing`
Reviewers: `code-reviewing`, `security-auditor`, `test-master`
Files to read: `app/services/weekly_reports.py`, `app/storage/weekly_report_drafts.py`, `app/sheets/gateway.py`
Files to modify: `app/services/weekly_reports.py`, `tests/test_weekly_report_finalize.py`

### Wave 3: Regression Coverage

#### Task 7: Weekly report boundary regression tests

Description: Add focused regression tests for late reports, duplicate reports, invalid drafts, cross-participant step selection, missing data notifications, and excluded feature boundaries. This wave protects the MVP storage and scope decisions before audit.

Skill: `test-master`
Reviewers: `code-reviewing`, `security-auditor`
Files to read: `work/weekly-report-flow/user-spec.md`, `app/services/weekly_reports.py`, `app/sheets/gateway.py`, `app/storage/weekly_report_drafts.py`
Files to modify: `tests/test_weekly_report_boundaries.py`

### Audit Wave

#### Task 8: Code Audit

Description: Review all weekly-report-flow implementation code for correctness, maintainability, boundary fit, and regressions against participant-core-flows. Write findings and required fixes before final QA.

Skill: `code-reviewing`
Reviewers: none
Files to read: `work/weekly-report-flow/user-spec.md`, `work/weekly-report-flow/tech-spec.md`, `app`, `tests`
Files to modify: `work/weekly-report-flow/logs/working/task-8/code-audit.json`

#### Task 9: Security Audit

Description: Review the feature for participant isolation, consent gating, secret leakage, sensitive report text handling, admin notification content, SQLite draft cleanup, and Sheets write boundaries. Write findings and required fixes before final QA.

Skill: `security-auditor`
Reviewers: none
Files to read: `work/weekly-report-flow/user-spec.md`, `work/weekly-report-flow/tech-spec.md`, `app`, `tests`
Files to modify: `work/weekly-report-flow/logs/working/task-9/security-audit.json`

#### Task 10: Test Audit

Description: Review weekly-report-flow tests for meaningful assertions, edge coverage, fixture quality, and acceptance-criteria traceability. Write findings and required fixes before final QA.

Skill: `test-master`
Reviewers: none
Files to read: `work/weekly-report-flow/user-spec.md`, `work/weekly-report-flow/tech-spec.md`, `tests`
Files to modify: `work/weekly-report-flow/logs/working/task-10/test-audit.json`

### Final Wave

#### Task 11: Pre-deploy QA

Description: Run acceptance verification against the user-spec and tech-spec, including the full local test suite and scope-boundary checks. This feature has no deploy or post-deploy step.

Skill: `pre-deploy-qa`
Reviewers: none
Files to read: `work/weekly-report-flow/user-spec.md`, `work/weekly-report-flow/tech-spec.md`, `work/weekly-report-flow/logs/working/task-8/code-audit.json`, `work/weekly-report-flow/logs/working/task-9/security-audit.json`, `work/weekly-report-flow/logs/working/task-10/test-audit.json`
Files to modify: `work/weekly-report-flow/logs/working/task-11/pre-deploy-qa.json`

## Agent Verification Plan

| Check | Command / Tool | Expected result |
|-------|----------------|-----------------|
| Full test suite | `.venv/bin/python -m pytest -q` | All tests pass without production secrets |
| Green flow | pytest integration test | WeeklyReport green/🟩/1, closed relations, selected planned steps closed, draft cleared |
| Blue flow | pytest integration test | WeeklyReport blue/🟦/0.5, partial relations, planned steps unchanged, draft cleared |
| Red flow | pytest integration test | WeeklyReport red/🟥/0, no required step relations, planned steps unchanged, draft cleared |
| Deadline guard | pytest unit/integration test | Late save after Sunday 23:59 Yekaterinburg creates no final facts |
| Duplicate guard | pytest integration test | Same participant/week second save is rejected |
| Storage boundary | pytest/static check | Final facts only through Sheets fake; SQLite stores only technical draft state |
| Scope boundary | pytest/static check | No live Telegram/Google adapter, scheduler reminders, voice, PDF, deploy, Docker, Redis, or Celery added |

## Approval Gate

After this tech-spec is approved, decompose it into task files under `work/weekly-report-flow/tasks/`. Do not write application code for weekly-report-flow until the approved tech-spec and task decomposition are committed.
