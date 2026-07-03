---
created: 2026-07-03
status: approved
branch: dev
size: M
---

# Tech Spec: captain-flows

## Solution

Implement captain flows as a captain-specific service layer that reuses the existing weekly report business model instead of creating a separate report type. Captains will be resolved through the existing Telegram ID and consent boundaries, then authorized by `role = captain` and `team_id`.

The feature adds a service for captain team reads and captain manual weekly report drafts. The final business write remains a row in `weekly_reports` plus optional `weekly_report_steps`, with the selected participant as `participant_id` and the captain as `submitted_by_id` / `submitted_by_role = captain`.

SQLite remains technical state only. It stores the captain's selected participant, selected status, selected steps, ordered text/voice draft fragments, and active dialog state until successful final save. Google Sheets remains the only final business storage.

The feature is local/fake-boundary based. It does not add live Telegram SDK handlers, deploy configuration, captain PDF delivery, report generation, web forms, PostgreSQL, Docker, Redis, Celery, or a web admin panel.

## Architecture

### What we're building/modifying

- **Captain service** — new business service for captain-only team view and manual weekly report flow.
- **Captain models** — small read models for own-team participant rows and manual report flow responses if needed.
- **Google Sheets boundary extension** — query helpers for participants by team and participant id so the service does not scan internal fake state or trust callback payloads.
- **Weekly report draft repository extension** — captain manual draft creation that stores selected participant and captain submitter metadata while reusing ordered draft messages, selected status, selected steps, and voice attachment storage.
- **Dialog state usage** — `flow = captain_manual_report` and `selected_participant_id` track the captain's active manual report flow.
- **Bot copy/menu contracts** — captain-safe Russian copy for own-team view, forbidden selection, dropped participant, duplicate report, deadline, and success states.
- **Tests** — captain service, sheets boundary, SQLite draft, weekly report regressions, and role/privacy boundary tests.

### How it works

1. A captain starts from the existing role-aware menu.
2. `CaptainService` resolves the Telegram user through `SheetsGateway.find_participant_by_telegram_id(...)`.
3. The service requires consent, `role = captain`, and a non-empty captain `team_id`.
4. For own-team view, the service lists participants whose `team_id` matches the captain's team and formats a role-safe Telegram response.
5. For manual report start, the service receives a selected participant id and reloads that participant from Google Sheets.
6. The service rejects the selected participant if they are not in the captain's team, are dropped/inactive, already have a report for the current week, or lack active goal/planned step data.
7. The service creates a captain manual draft in SQLite and stores `selected_participant_id` in `dialog_states`.
8. Status selection and step selection follow the existing weekly report semantics: green/blue require selected planned step IDs, red does not.
9. Text messages append ordered draft messages. Voice input can reuse `VoiceMessageService` after the draft repository exposes captain manual report as a voice-capable weekly report draft; if this proves too broad during implementation, the task may keep voice rejected with safe copy and record the deviation for user approval.
10. Finalization revalidates captain role, own-team ownership, deadline, duplicate report, active goal, selected status, selected steps, and non-empty text.
11. The service appends a `weekly_reports` row for the selected participant with `submitted_by_id` equal to the captain participant id, `submitted_by_role = captain`, and `flow_source = captain_manual`.
12. For green/blue, it appends `weekly_report_steps`; for green, it closes selected planned steps.
13. The service clears the technical draft after successful final save.
14. Technical failures notify only admin error chat through `NotificationRouter`.

### Shared resources

No heavy singleton resources are added.

| Resource | Owner (creates) | Consumers | Instance count |
|----------|-----------------|-----------|----------------|
| SQLite database path | application composition / tests | `DialogStateRepository`, weekly draft repository, captain service | 1 path per runtime |
| `SheetsGateway` | application composition / tests | participant, weekly report, insight, captain services | 1 gateway per service graph |
| `NotificationRouter` | application composition / tests | participant, weekly report, insight, voice, captain services | 1 router per service graph |

## Decisions

### Decision 1: Captain manual reports stay weekly reports
**Decision:** A captain manual report writes to `weekly_reports` and `weekly_report_steps`, not a new business table.
**Rationale:** Supports US-AC11, US-AC12, and US-AC13. Reports and scheduler phases need one weekly status source.
**Alternatives considered:** Add a separate captain report table. Rejected because it would duplicate progress/reporting logic and complicate later summaries.

### Decision 2: Use a separate captain service
**Decision:** Add `CaptainService` instead of overloading `WeeklyReportService` with selected-participant behavior.
**Rationale:** Supports US-AC1, US-AC2, US-AC3, and US-AC12. Participant weekly reports resolve the reporting participant from the current user; captain reports must resolve one user as submitter and another as report subject.
**Alternatives considered:** Add optional `selected_participant_id` parameters to `WeeklyReportService`. Rejected because it would make participant flow authorization easier to weaken.

### Decision 3: Server-side ownership checks on every selected participant
**Decision:** Every captain participant selection is reloaded and checked against the captain's `team_id`.
**Rationale:** Supports US-AC2 and US-AC3 and mitigates callback tampering.
**Alternatives considered:** Trust callback payloads generated from the own-team list. Rejected because callbacks can be forged.

### Decision 4: Existing deadline and duplicate semantics remain authoritative
**Decision:** Manual captain reports use `is_weekly_report_open(now)`, current challenge week, and `find_weekly_report(...)` before draft creation and final save.
**Rationale:** Supports US-AC5 and US-AC6 and preserves project decisions: no late/yellow status and no duplicate weekly report.
**Alternatives considered:** Allow captain recovery after deadline. Rejected because product decisions explicitly forbid status-changing captain reports after deadline.

### Decision 5: SQLite stores only captain draft state
**Decision:** Captain selected participant, selected status, selected steps, draft messages, and attachments stay in SQLite until successful save.
**Rationale:** Supports US-AC14 and US-AC15 while preserving Google Sheets as final storage.
**Alternatives considered:** Save partial captain reports directly to Google Sheets. Rejected because incomplete drafts are not business facts.

### Decision 6: Captain PDF access is out of this feature
**Decision:** Do not implement captain PDF access in captain-flows.
**Rationale:** Supports the user-spec Technical Decision that report delivery belongs to the reports phase.
**Alternatives considered:** Add `VIEW_TEAM_REPORT` now. Rejected to keep this feature focused on team view and manual weekly reporting.

## Data Models

### New service models

Expected in `app/services/captains.py` or similarly scoped module:

- `CaptainTeamMember`
  - `participant_id: str`
  - `display_name: str`
  - `team_id: str`
  - `is_dropped: bool`
  - optional status/progress fields if already available from Sheets rows
- `CaptainManualReportContext`
  - `captain: SheetRow`
  - `captain_id: str`
  - `target_participant: SheetRow`
  - `target_participant_id: str`
  - `team_id: str`
  - `goal: SheetRow`
  - `week_number: int`

Exact names may vary during implementation, but the service boundary must keep captain submitter and target participant separate.

### Sheets gateway additions

Extend `SheetsGateway` and `FakeSheetsGateway` with helpers equivalent to:

- `get_participant(participant_id: str) -> SheetRow | None`
- `list_participants_by_team(team_id: str) -> list[SheetRow]`

These helpers return row copies and are used for server-side authorization. The fake gateway must not expose internal mutable rows.

### SQLite draft state

Use existing tables where possible:

- `dialog_states.flow = 'captain_manual_report'`
- `dialog_states.selected_participant_id = target participant id`
- `draft_sessions.draft_type = 'captain_manual_report'`
- `draft_reports.flow_source = 'captain_manual'`
- `draft_reports.submitted_by_id = captain participant id`
- `draft_reports.submitted_by_role = 'captain'`
- `draft_messages` for ordered text and voice transcription fragments
- `draft_attachments` for accepted voice metadata if voice is enabled for captain manual drafts

No new SQLite tables are required unless implementation discovers a schema constraint that cannot represent captain submitter and selected participant safely. Any schema addition must remain technical-state only.

### Final Google Sheets rows

Captain manual report finalization writes:

- `weekly_reports.participant_id` = selected participant id
- `weekly_reports.team_id` = selected participant team id
- `weekly_reports.goal_id` = selected participant active goal id
- `weekly_reports.week_number` = current challenge week
- `weekly_reports.status_code`, `status_symbol`, `score`
- `weekly_reports.report_text`
- `weekly_reports.transcription_text`, `audio_file_path`, `audio_deleted_at`
- `weekly_reports.submitted_by_id` = captain participant id
- `weekly_reports.submitted_by_role` = `captain`
- `weekly_reports.flow_source` = `captain_manual`

For green/blue, write `weekly_report_steps` with the selected participant id and selected goal id. For green, close selected planned steps for the selected participant.

## Dependencies

### New packages

- None.

### Using existing (from project)

- `app.bot.menus` — captain menu action contracts.
- `app.bot.messages` — Russian copy constants and formatting helpers.
- `app.scheduler.calendar` — current week and Sunday 23:59 Yekaterinburg deadline helpers.
- `app.services.notifications` — admin-only technical error routing.
- `app.services.participant_models` — `TelegramUserContext`, `FlowResponse`, menu item models.
- `app.services.weekly_report_models` — weekly status enum, score, symbols.
- `app.services.voice_messages` — optional voice input boundary for active captain manual report drafts.
- `app.sheets.gateway` — business data boundary and fake gateway.
- `app.storage.dialog_state` — active captain flow and selected participant state.
- `app.storage.weekly_report_drafts` — technical draft repository, extended for captain manual report source metadata.

## Testing Strategy

**Feature size:** M

### Unit tests

- Captain menu actions remain visible only for `role = captain`.
- Captain copy constants are Russian, safe, and do not expose internal IDs.
- Team member formatter does not leak other-team rows.
- Dropped/active participant detection handles expected sheet values.

### Integration tests

- Captain can list only own-team participants.
- Non-captain cannot start captain team view or manual report.
- Captain cannot select another team's participant, including forged callback IDs.
- Captain cannot report for dropped participant.
- Captain cannot start or finalize a duplicate report for participant/week.
- Captain cannot finalize after weekly deadline.
- Green and blue captain reports require selected step IDs.
- Red captain report does not create weekly_report_steps.
- Already closed steps cannot be selected for green.
- Successful green report writes `weekly_reports`, `weekly_report_steps`, closes steps, and clears SQLite draft.
- Successful blue report writes partial step relations without closing steps.
- Final row uses selected participant as report subject and captain as submitter.
- Google Sheets/SQLite failure preserves draft and routes technical details only to admin error chat.
- Existing participant weekly report tests continue to pass unchanged.

### E2E tests

- None in this local feature. Live Telegram callback handling and production smoke are deferred to deployment/post-deploy work.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Verify locally with pytest, fake Google Sheets, temporary SQLite, and fake bot clients. No deploy, live Telegram bot, live Google Sheets, real transcription provider, or secrets are required.

### Tools required

- bash / pytest
- Python standard library SQLite and filesystem
- No Playwright MCP, Telegram MCP, curl, deploy, or live external API calls for this feature draft.

## Risks

| Risk | Mitigation |
|------|------------|
| Captain sees or reports for another team | Reload selected participant by id and check `team_id` on every action and final save. |
| Captain manual report bypasses deadline/duplicate guards | Reuse calendar helper and Sheets duplicate lookup at start and finalization. |
| Submitter and report subject are mixed up | Keep explicit captain vs target participant context models and assert final row fields in tests. |
| Business facts remain only in SQLite | Clear draft only after successful Google Sheets write; final facts are weekly report rows. |
| Step selection closes invalid or already closed steps | Filter and revalidate selected planned steps before draft update and final save. |
| Voice support in captain manual drafts expands scope too much | Reuse existing voice boundary only if it fits draft repository extension; otherwise keep safe text fallback and record a user-approved deviation before implementation. |

## User-Spec Deviations

None.

## Acceptance Criteria

- [ ] `work/captain-flows/user-spec.md` status is approved before implementation tasks start.
- [ ] Captain-only flows require identified consenting user with `role = captain`.
- [ ] Own-team list and participant selection are always scoped by captain `team_id`.
- [ ] Forged selected participant IDs outside the captain team are rejected server-side.
- [ ] Dropped participants cannot receive captain manual reports.
- [ ] Duplicate participant/week reports are rejected.
- [ ] Captain manual reports cannot be finalized after the weekly deadline.
- [ ] Green/blue captain reports require valid selected planned step IDs.
- [ ] Red captain reports do not create weekly_report_steps.
- [ ] Green captain reports close selected planned steps; blue reports create partial relations without closing them.
- [ ] Final weekly report rows store selected participant as report subject and captain as submitter.
- [ ] SQLite stores only temporary captain draft state and is cleared after successful final save.
- [ ] Technical errors route only through admin error chat.
- [ ] No web form, PostgreSQL, Docker, Redis, Celery, web admin panel, participant-created steps, past-week editing, or late/yellow status is added.
- [ ] Full local pytest suite passes.

## Implementation Tasks

### Wave 1 (foundations)

#### Task 1: Captain messages and sheets boundary
- **Description:** Add captain-safe Russian copy and Google Sheets boundary helpers for own-team participant reads. This creates the service inputs needed for role-safe team view and participant selection without exposing fake gateway internals.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_participant_messages.py tests/test_participant_sheets_gateway.py -q` -> pass
- **Files to modify:** `app/bot/messages.py`, `app/sheets/gateway.py`, `tests/test_participant_messages.py`, `tests/test_participant_sheets_gateway.py`
- **Files to read:** `app/bot/menus.py`, `work/captain-flows/user-spec.md`

#### Task 2: Captain manual draft repository support
- **Description:** Extend weekly report draft storage so captain manual report drafts can store the selected participant and captain submitter metadata as technical state. This keeps captain draft state in SQLite while preserving final business writes in Google Sheets.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py tests/test_sqlite_schema.py -q` -> pass
- **Files to modify:** `app/storage/weekly_report_drafts.py`, `tests/test_weekly_report_draft_repository.py`, `tests/test_sqlite_schema.py`
- **Files to read:** `app/storage/sqlite.py`, `app/storage/dialog_state.py`, `work/captain-flows/user-spec.md`

### Wave 2 (captain service)

#### Task 3: Captain team view service
- **Description:** Add captain service behavior for resolving captain identity, consent, role, and own-team participant list. This gives captains the team visibility required for manual report selection while denying non-captains and cross-team access.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_captain_team_flow.py tests/test_participant_boundaries.py -q` -> pass
- **Files to modify:** `app/services/captains.py`, `tests/test_captain_team_flow.py`
- **Files to read:** `app/services/participant_flows.py`, `app/services/notifications.py`, `app/sheets/gateway.py`, `app/bot/messages.py`

#### Task 4: Captain manual report flow
- **Description:** Implement captain manual report start, status selection, step selection, text input, and finalization for own-team participants. The flow writes normal weekly report facts with captain submitter metadata and reuses existing deadline, duplicate, status, and step semantics.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_captain_manual_report_flow.py tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py -q` -> pass
- **Files to modify:** `app/services/captains.py`, `app/storage/weekly_report_drafts.py`, `tests/test_captain_manual_report_flow.py`, `tests/test_weekly_report_finalize.py`, `tests/test_weekly_report_boundaries.py`
- **Files to read:** `app/services/weekly_reports.py`, `app/services/weekly_report_models.py`, `app/scheduler/calendar.py`, `app/sheets/gateway.py`

### Wave 3 (cross-flow regressions)

#### Task 5: Captain boundary regression coverage
- **Description:** Add cross-flow regressions for forged participant IDs, dropped participants, duplicate reports, deadline denial, invalid step selection, and out-of-scope dependency boundaries. This protects captain manual reports from role leakage and business-rule bypass.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_captain_boundaries.py tests/test_boundaries.py -q` -> pass
- **Files to modify:** `tests/test_captain_boundaries.py`, `tests/test_boundaries.py`
- **Files to read:** `app/services/captains.py`, `app/storage/weekly_report_drafts.py`, `tests/test_participant_boundaries.py`

### Audit Wave

#### Task 6: Code Audit
- **Description:** Full-feature code quality audit for captain-flows source and tests. Review service boundaries, weekly report reuse, storage responsibilities, and consistency with approved architecture.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 7: Security Audit
- **Description:** Full-feature security audit for role checks, team scoping, callback tampering, personal data exposure, admin-only errors, and forbidden dependency additions. Write a structured audit report.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 8: Test Audit
- **Description:** Full-feature test quality audit for captain team view, manual report flow, and boundary regressions. Verify behavior-oriented assertions and coverage for role/deadline/step edge cases.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 9: Pre-deploy QA
- **Description:** Run full local acceptance testing for captain-flows and verify all user-spec and tech-spec acceptance criteria with fake/local boundaries. Confirm no deploy, live Telegram, live Google Sheets, generated credentials, or production secrets are required.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `.venv/bin/python -m pytest -q` -> pass
- **Files to modify:** `work/captain-flows/logs/working/task-9/pre-deploy-qa.json`, `work/captain-flows/tasks/9.md`, `work/captain-flows/decisions.md`
- **Files to read:** `work/captain-flows/user-spec.md`, `work/captain-flows/tech-spec.md`, `work/captain-flows/tasks/`, `work/captain-flows/logs/working/`
