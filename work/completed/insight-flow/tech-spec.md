---
created: 2026-07-02
status: approved
branch: main
size: M
---

# Tech Spec: insight-flow

## Summary

Implement an adapter-independent personal insight flow for participants. The feature activates the existing `💡 Мои инсайты` menu action, supports adding current-week text insights, stores temporary insight drafts in SQLite technical state, writes final Insight facts through the Google Sheets boundary, and lets participants list, paginate, and open only their own saved insights.

This spec intentionally excludes real voice transcription, live Telegram SDK wiring, live Google API adapter work, captain team insight views, scheduler/report integration, PDF generation, deploy, push, and production actions.

## User-Spec Requirements Mapping

| ID | Requirement |
|----|-------------|
| US-1 | `💡 Мои инсайты` opens a personal insight menu with add and list actions. |
| US-2 | Unknown users and non-consenting users cannot add or view insights. |
| US-3 | Captains use this feature only for their own personal insights. |
| US-4 | Add flow creates SQLite draft state and saves final facts only after completion. |
| US-5 | Added insights are current-week only, with `week_number`, `insight_scope = current_week`, and `insight_date`. |
| US-6 | Final Insight includes `insight_title` and `insight_date`, requiring Google Sheets schema extension. |
| US-7 | Missing active goal blocks save with approved Russian copy. |
| US-8 | Empty draft finalization creates no final Insight and asks the user to repeat. |
| US-9 | Ordered text messages are assembled into `insight_text`. |
| US-10 | Title prompt, 120-character title limit, and skip fallback title are supported. |
| US-11 | Successful save returns `Инсайт сохранён.`, clears draft, and returns role-aware menu. |
| US-12 | Duplicate finalization is idempotent and creates no duplicate Insight. |
| US-13 | Cancel clears draft and saves no Insight. |
| US-14 | List view shows only current participant insights, latest 10 first, with bounded pagination. |
| US-15 | Full-text callback is participant-scoped by `insight_id`; missing/stale callback is safe and admin-notified. |
| US-16 | Insight flow does not change weekly reports, steps, status, score, scheduler, PDF, voice records, or deploy state. |
| US-17 | Tests run locally without production tokens, Google credentials, transcription provider, live Telegram, or network. |

## Architecture

### What we're building/modifying

- **Insight message contracts** — Russian copy constants and formatting helpers for menu, add flow, validation, list pages, full text, and safe error responses.
- **Insight domain models** — typed scope, draft, final row, list item, pagination, and callback response contracts.
- **Google Sheets insight boundary** — extend `SheetsGateway` and `FakeSheetsGateway` with participant-scoped insight list/get operations while preserving existing append/list behavior.
- **SQLite insight draft repository** — repository over existing `draft_sessions`, `dialog_states`, `draft_insights`, and `draft_messages`.
- **Insight service** — adapter-independent orchestration for menu, add text draft, title, skip title, finalize, cancel, list page, and full-text callback.
- **Participant flow integration** — remove `VIEW_INSIGHTS` from inert handling and route it to insight menu behavior at service level.
- **Tests** — unit/integration tests for copy, Sheets scoping, draft persistence, service flows, pagination, callback privacy, and out-of-scope boundaries.

### How it works

1. Future Telegram adapter or tests call the insight service with `TelegramUserContext`.
2. The service resolves the participant by Telegram ID through `SheetsGateway`.
3. Unknown users receive the approved unknown-user text and admin error notification.
4. Non-consenting users receive the approved consent text and cannot access insight data.
5. `show_menu` returns `➕ Добавить инсайт` and `📜 Посмотреть инсайты`.
6. `start_add` requires an active goal, calculates current challenge week using `current_challenge_week_number(now)`, sets `insight_scope = current_week`, sets `insight_date` from `now` in `Asia/Yekaterinburg`, and creates an SQLite insight draft.
7. `add_text_message` appends ordered draft text messages.
8. `finalize_without_title` or equivalent step validates non-empty text and asks for `Как кратко озаглавить твой инсайт?`.
9. `set_title` validates title length up to 120 characters.
10. `skip_title` derives title from the first 80-100 characters of assembled insight text.
11. Final save uses a deterministic `insight_id` derived from the draft identity or another stable idempotency key, appends one Insight row through Sheets, marks the draft/session as saved, clears active dialog state, and returns `Инсайт сохранён.` plus role-aware menu metadata.
12. Repeated finalization after a successful save checks the saved marker or existing participant-scoped `insight_id`, returns `Инсайт уже сохранён.`, and appends no new row.
13. `cancel` clears the active insight draft and returns role-aware menu metadata.
14. `list_insights(page)` returns current participant insights only, sorted newest-first by `insight_date` and `created_at`, 10 per page.
15. `get_full_text(insight_id)` resolves by current `participant_id` and `insight_id`. If missing or stale, it returns `Инсайт не найден.` and sends a technical admin notification.

### Shared resources

None. The feature uses injected gateway/repository/router/bot boundaries and short-lived SQLite connections. It introduces no new API clients, connection pools, ML models, browser instances, background workers, or shared external services.

## Data Models

### Google Sheets `Insights` schema extension

Existing `Insights` columns remain valid. Add:

- `insight_title`
- `insight_date`

Final Insight row prepared by the service:

- `insight_id`
- `participant_id`
- `goal_id`
- `week_number`
- `insight_scope`: always `current_week` in this feature
- `insight_title`
- `insight_date`
- `insight_text`
- `transcription_text`: empty in this feature, reserved for future voice processing
- `audio_file_path`: empty in this feature, reserved for future voice processing
- `audio_deleted_at`: empty in this feature
- `created_by_id`
- `created_by_role`: `participant` or `captain`
- `created_at`

### Sheets gateway additions

Add protocol/fake methods:

- `list_insights_for_participant(participant_id: str) -> list[SheetRow]`
- `get_participant_insight(participant_id: str, insight_id: str) -> SheetRow | None`

Keep existing:

- `append_insight(row: SheetRow) -> None`
- `list_insights() -> list[SheetRow]`

Fake gateway must return defensive copies and sort only in service/formatter unless a method explicitly documents ordering.

### SQLite draft state

Use existing tables:

- `draft_sessions.draft_type = "insight"`
- `dialog_states.flow = "insight"`
- `draft_insights.insight_scope = "current_week"`
- `draft_messages.message_type = "text"`

Extend the technical `draft_insights` table with nullable fields if needed:

- `insight_title`
- `saved_insight_id`
- `saved_at`

These fields are technical draft/idempotency metadata, not final business storage. Active dialog state is cleared after save/cancel; a short-lived saved marker may remain in `draft_sessions`/`draft_insights` only to make duplicate finalization idempotent.

### Python models

Recommended models:

- `InsightScope`: enum/details for `current_week`.
- `InsightDraft`: active or recently saved draft snapshot with draft ID, participant ID, goal ID, week number, scope, assembled text, optional title, message count, timestamps, and saved marker.
- `InsightListItem`: insight ID, date, title, preview, has full text callback.
- `InsightPage`: items, page index, page size, total count, has older, has newer.
- `InsightServiceResponse`: `FlowResponse` or existing `FlowResponse` with text/buttons/menu metadata.

## Dependencies

### New packages

None.

### Using existing (from project)

- `app.bot.messages` — Russian copy and formatters.
- `app.bot.menus` — `MenuAction.VIEW_INSIGHTS`, participant/captain role menu definitions.
- `app.services.participant_models` — `TelegramUserContext`, `FlowResponse`, `MenuItem`.
- `app.services.notifications` — technical admin notification routing.
- `app.sheets.gateway` — Sheets protocol and fake storage.
- `app.storage.sqlite` — existing draft/dialog schema.
- `app.scheduler.calendar` — approved `Asia/Yekaterinburg` challenge week helper.
- `app.storage.weekly_report_drafts` — implementation pattern for draft repositories.

## Decisions

### Decision 1: Keep insight-flow adapter-independent
**Decision:** Implement service-level insight behavior and boundary methods, not live Telegram SDK handlers.  
**Rationale:** Supports US-17 and the user-spec exclusion of live Telegram SDK, live Google API adapter, deploy, and production actions.  
**Alternatives considered:** Wire real Telegram callbacks now. Rejected because runtime adapters are not needed to verify MVP business logic and would expand scope.

### Decision 2: Extend Google Sheets `Insights` with `insight_title` and `insight_date`
**Decision:** Add first-class final fields instead of embedding title/date in `insight_text` or relying only on `created_at`.  
**Rationale:** Supports US-6 and list/report readability. `created_at` is technical save time; `insight_date` is user-facing report/list date.  
**Alternatives considered:** Use first line of `insight_text` as title and `created_at` as date. Rejected because it makes reports fragile and mixes content with metadata.

### Decision 3: Current-week-only add flow
**Decision:** Service always writes `insight_scope = current_week` and current `week_number`; previous-week and goal-general add scopes are not offered.  
**Rationale:** Supports US-5 and the approved user decision for the current challenge run.  
**Alternatives considered:** Keep the older docs' three-scope selector. Rejected because the user explicitly narrowed add flow to current week.

### Decision 4: Participant-scoped list and full-text callbacks
**Decision:** Every list/get operation resolves current Telegram ID and filters by current `participant_id`. Full-text callback uses both `participant_id` and `insight_id`.  
**Rationale:** Supports US-3, US-14, US-15, and privacy constraints.  
**Alternatives considered:** Lookup full text by `insight_id` only. Rejected because guessed/stale callback IDs could expose another participant's text.

### Decision 5: SQLite stores only temporary insight draft state
**Decision:** Use existing draft tables for active drafts, extend them only with technical title/idempotency fields if needed, and clear active dialog state after save/cancel/recovery. Final Insight facts are written only through Sheets.  
**Rationale:** Supports US-4 and storage boundary requirements.  
**Alternatives considered:** Add local final `insights` table. Rejected because SQLite must not become business storage.

### Decision 6: Defer real voice processing
**Decision:** Voice messages receive a not-yet-available response and create no audio/transcription/final voice facts in this feature.  
**Rationale:** Supports US-16 and the user-approved split where `voice-processing` later serves weekly reports and insights.  
**Alternatives considered:** Implement voice for insights now. Rejected because it would duplicate future shared voice infrastructure.

### Decision 7: Idempotent duplicate finalization
**Decision:** A second finalization after successful save returns `Инсайт уже сохранён.` and creates no duplicate row by checking a saved draft marker or existing participant-scoped deterministic `insight_id`.  
**Rationale:** Supports US-12 and prevents accidental double-click duplicates.  
**Alternatives considered:** Treat second click as missing draft. Rejected because the user requested explicit duplicate-save feedback.

### Decision 8: No deploy or post-deploy verification
**Decision:** This feature ends at local pre-deploy QA.  
**Rationale:** Supports project deployment constraints and user-spec exclusions.  
**Alternatives considered:** Deploy immediately after implementation. Rejected because all deployment must be explicitly approved and go through GitHub CI/CD.

## Error Handling

- Unknown user: existing approved unknown-user text and admin technical notification.
- Consent missing: approved consent text; no insight data is shown.
- Missing active goal: return `Прости, у тебя не зафиксировано активной цели, обратись к капитану`; no Insight row is saved.
- Empty finalization: return `Я не получил текст инсайта. Отправь инсайт текстом и нажми ✅ Готово.`; draft remains active.
- Title too long: ask the participant to shorten; no final Insight row is saved yet.
- Voice message: return a short not-yet-available text and ask for text; no voice/audio state is created.
- Cancel: clear active insight draft and return role-aware menu metadata.
- Duplicate finalization after successful save: use a saved marker or existing deterministic `insight_id`; return `Инсайт уже сохранён.`; no duplicate row.
- Missing/stale full-text callback: return `Инсайт не найден.` and notify admin without exposing full insight text or secrets.
- Sheets write failure: keep draft recoverable when possible and notify admin; do not report success to the user.
- Invalid/stale draft state: clear unsafe state when needed, return safe recovery/menu response, and notify admin.

## Security and Privacy

- Consent is required before add/list/full-text operations.
- Current Telegram ID is re-resolved through Sheets for protected operations.
- Full insight text is never exposed through public URLs.
- Full-text callback must be scoped by participant ID and insight ID.
- Admin technical notifications must not include secrets, tokens, credentials, or unnecessary full insight text.
- Captains cannot view team participant insights in this feature.
- SQLite may temporarily contain draft insight text until save/cancel/recovery; it must not store final business facts.
- No live Telegram token, Google credential, transcription provider key, or production sheet is required for tests.

## Testing Strategy

**Feature size:** M

### Unit tests

- Insight menu/copy constants for add/list/cancel/title/empty/success/duplicate/missing insight/missing goal.
- Insight title validation: <=120 accepted, >120 rejected, skip fallback uses first 80-100 characters.
- Insight list formatting: date, title, preview, `читать целиком`, and long-text truncation.
- Pagination helper: latest 10 first, older/newer flags, boundary pages.
- Insight ID and callback payload helpers if introduced.

### Integration tests

- Unknown user cannot access insights and routes admin technical notification.
- Non-consenting user cannot add/list/full-text insights.
- Current-week text insight save writes exactly one final row with `insight_title`, `insight_date`, `insight_scope = current_week`, and ordered `insight_text`.
- Missing active goal blocks save with approved copy and writes no Insight row.
- Empty draft finalization writes no Insight row and keeps draft active.
- Cancel clears draft and writes no Insight row.
- Duplicate finalization creates no duplicate and returns `Инсайт уже сохранён.`.
- Personal list returns only current participant insights, latest 10 first.
- Pagination over 16 insights returns two bounded pages.
- Full-text callback returns own full text and rejects another participant's insight.
- Stale/missing callback returns `Инсайт не найден.` and sends admin technical notification.
- Voice message creates no audio/transcription/final voice state.
- Insight save does not create WeeklyReports, WeeklyReportSteps, planned-step closure, status, score, scheduler jobs, PDF files, deploy artifacts, or live SDK dependencies.

### E2E tests

None. Live Telegram callback rendering, live Google Sheets, voice provider, and production deployment are out of scope for this feature.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Agent verifies locally with pytest, fake Sheets, fake bot clients, and temporary SQLite databases. Static tests/checks verify that no live SDKs, voice processing, scheduler, PDF, deploy, or business SQLite storage are introduced.

### Tools required

- bash
- pytest
- python local commands

No Telegram MCP, Playwright MCP, curl to external services, live Google API, deploy tool, or server access is required.

## Risks

| Risk | Mitigation |
|------|------------|
| Schema mismatch for `insight_title` and `insight_date` | Document both fields in user-spec, tech-spec, and task scope; gateway tests assert final rows include them. |
| Full-text callback leaks another participant's insight | Resolve current Telegram ID and call participant-scoped get by `participant_id` + `insight_id`. |
| Feature expands into real voice processing | Voice messages return not-yet-available copy and tests assert no voice/audio/transcription state is created. |
| Captains receive team insights too early | Treat captain as personal participant in this feature and test cross-participant isolation. |
| Pagination floods chat or breaks on bounds | Page size fixed at 10, helper tests cover first/last/out-of-range pages. |
| SQLite becomes final insight storage | Repository stores only active draft state; final rows go through Sheets gateway only. |

## User-Spec Deviations

None.

## Acceptance Criteria

- [ ] `MenuAction.VIEW_INSIGHTS` is no longer handled as inert for insight-flow.
- [ ] Insight service exposes add/list/full-text/cancel/finalize behavior without live Telegram SDK wiring.
- [ ] Unknown and non-consenting users cannot add/list/open insights.
- [ ] Captain users are scoped to their own participant ID only.
- [ ] Sheets gateway supports participant-scoped insight listing and lookup.
- [ ] Final Insight rows include `insight_title` and `insight_date`.
- [ ] Final Insight rows use `insight_scope = current_week`.
- [ ] Missing active goal writes no Insight row and returns the approved custom copy.
- [ ] SQLite draft repository uses technical draft tables, may add technical title/idempotency fields, and clears active draft state after save/cancel.
- [ ] Ordered draft text messages become final `insight_text`.
- [ ] Title length, skip fallback, empty draft, cancel, duplicate finalization, stale callback, and pagination boundaries are covered by tests.
- [ ] Full-text callback cannot return another participant's insight.
- [ ] No WeeklyReport, WeeklyReportSteps, planned-step closure, weekly status, score, scheduler job, PDF, audio file, transcription row, live SDK, deploy, or production action is introduced.
- [ ] Full local pytest suite passes without production secrets or network.

## Implementation Tasks

### Wave 1: Contracts and Boundaries

#### Task 1: Insight message and model contracts
- **Description:** Add insight-specific Russian copy, list formatting helpers, scope/title/page models, and callback-safe response contracts. This gives the service a stable user-facing and testable contract.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, test-reviewer
- **Files to modify:** `app/bot/messages.py`, `app/services/insight_models.py`, `tests/test_insight_messages.py`
- **Files to read:** `work/insight-flow/user-spec.md`, `app/bot/messages.py`, `app/services/participant_models.py`, `.codex/skills/project-knowledge/references/ux-guidelines.md`

#### Task 2: Insight Sheets boundary
- **Description:** Extend the Sheets protocol and fake gateway with participant-scoped insight list/get operations and final row expectations for `insight_title` and `insight_date`. This keeps final Insight facts inside the approved Google Sheets boundary.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/sheets/gateway.py`, `tests/test_insight_sheets_gateway.py`
- **Files to read:** `app/sheets/gateway.py`, `docs/04_google_sheets_schema.md`, `work/insight-flow/user-spec.md`

#### Task 3: Insight draft repository
- **Description:** Add a SQLite repository for insight draft sessions, ordered text messages, title state, active/recently-saved draft loading, saved/idempotency handling, and draft clearing. The repository uses technical tables and must not create final business storage.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/storage/sqlite.py`, `app/storage/insight_drafts.py`, `tests/test_sqlite_schema.py`, `tests/test_insight_draft_repository.py`
- **Files to read:** `app/storage/sqlite.py`, `app/storage/weekly_report_drafts.py`, `tests/test_weekly_report_draft_repository.py`, `docs/05_sqlite_state_schema.md`

### Wave 2: Insight Service Flow

#### Task 4: Insight menu, add flow, and final save
- **Description:** Implement the insight service operations for showing the insight menu, starting current-week drafts, collecting text, validating title, skip-title fallback, cancel, and final save. This creates the personal text insight business write path through Sheets.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/services/insights.py`, `app/services/participant_flows.py`, `tests/test_insight_add_flow.py`
- **Files to read:** `app/services/participant_flows.py`, `app/services/weekly_reports.py`, `app/services/notifications.py`, `app/scheduler/calendar.py`, `app/storage/insight_drafts.py`, `app/sheets/gateway.py`

#### Task 5: Insight list, pagination, and full-text callback
- **Description:** Implement participant-scoped insight listing, newest-first pagination, preview formatting, and full-text callback lookup. This completes the personal read path while protecting cross-participant privacy.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/services/insights.py`, `tests/test_insight_list_flow.py`
- **Files to read:** `app/services/insights.py`, `app/sheets/gateway.py`, `app/bot/messages.py`, `work/insight-flow/user-spec.md`

### Wave 3: Regression Coverage

#### Task 6: Insight boundary regression tests
- **Description:** Add focused tests for consent, captain personal scope, missing goal, empty draft, duplicate finalization, stale callback, voice exclusion, and out-of-scope business writes. This protects privacy, storage boundaries, and MVP scope before audit.
- **Skill:** test-master
- **Reviewers:** code-reviewer, security-auditor
- **Files to modify:** `tests/test_insight_boundaries.py`
- **Files to read:** `work/insight-flow/user-spec.md`, `app/services/insights.py`, `app/sheets/gateway.py`, `app/storage/insight_drafts.py`, `tests/test_weekly_report_boundaries.py`, `tests/test_participant_boundaries.py`

### Audit Wave

#### Task 7: Code Audit
- **Description:** Full-feature code quality audit for all insight-flow source and test files. Review architecture fit, duplication, draft lifecycle, callback flow, and regressions against participant and weekly report services.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 8: Security Audit
- **Description:** Full-feature security audit focused on consent, participant scoping, callback privacy, sensitive text handling, admin notifications, and storage boundaries. Write findings and required fixes before final QA.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 9: Test Audit
- **Description:** Full-feature test quality audit for insight-flow coverage. Verify meaningful assertions for add/list/full-text/pagination/scoping/empty/cancel/duplicate/stale-callback and out-of-scope exclusions.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 10: Pre-deploy QA
- **Description:** Run the full local test suite and verify user-spec and tech-spec acceptance criteria for insight-flow. No deploy, push, live Telegram, live Google API, voice provider, or production action is performed.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
