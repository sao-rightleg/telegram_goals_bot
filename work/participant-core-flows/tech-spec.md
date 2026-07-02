---
created: 2026-07-02
status: draft
branch: main
size: M
---

# Tech Spec: participant-core-flows

## Solution

Build the first executable participant-facing Telegram flow layer on top of `mvp-foundation`: `/start`, Telegram ID identification, unknown-user handling, consent, role-aware menu generation, and read-only goal/steps/progress views.

The feature stays adapter-independent. It introduces service-level flow orchestration and fake-backed boundaries that can be tested without live Telegram tokens, Google credentials, or production Google Sheets. Live Telegram SDK handlers and live Google API adapters remain outside this feature unless a later approved spec adds them.

Business facts stay in Google Sheets. SQLite is used only for technical dialog/menu state when needed. Technical errors and missing required data are routed through the existing error-bot notification boundary.

## Architecture

### What we're building/modifying

- **Participant domain models** — typed structures for participants, goals, planned steps, progress summaries, Telegram user context, menu items, and flow responses.
- **Google Sheets participant boundary** — extend `SheetsGateway` and `FakeSheetsGateway` with participant lookup by Telegram ID, consent write, active goal read, planned-step read, and weekly progress-history read.
- **Participant flow service** — orchestrates `/start`, consent acceptance, menu actions, user scoping, missing-data handling, and technical error notifications.
- **Telegram message templates** — central Russian copy and formatting helpers for approved texts, menus, read-only views, missing-data responses, and not-yet-available insight response.
- **Menu builder** — role-aware menu definitions for participant and captain roles.
- **SQLite dialog state repository** — small technical-state repository for writing the current participant/menu flow into `dialog_states` without storing final business facts.
- **Tests** — unit and integration tests for identification, consent, role menus, view rendering, participant scoping, missing data, error routing, and out-of-scope boundaries.

### How it works

Start flow:

1. Incoming adapter or test calls the participant flow service with Telegram ID, chat ID, username, and `/start`.
2. Service asks `SheetsGateway.find_participant_by_telegram_id`.
3. If no participant is found, service sends the approved unknown-user message through the main-bot boundary and sends one technical error notification through `NotificationRouter` with category `TECHNICAL_ERROR`.
4. If participant exists but consent is absent, service writes technical dialog state `flow='consent'` and returns/sends the approved consent text plus `✅ Согласен`.
5. If participant exists and consent is already present, service writes technical dialog state `flow='idle'` and returns/sends the role-aware menu.
6. Consent acceptance validates the Telegram ID again, writes `consent_given` and `consent_given_at` through Sheets, updates dialog state to idle, and returns/sends the role-aware menu.

Read-only menu actions:

1. Service resolves the current Telegram ID through Sheets for every view request.
2. Service requires consent before returning business data.
3. Goal view loads the current participant's active goal only.
4. Planned-steps view loads planned steps for the current participant and active goal only.
5. Progress view calculates planned-step progress from that participant's steps and appends weekly status history if already present in Sheets data.
6. If required data is missing, the participant receives a short neutral Russian message and admin error chat receives a technical notification without secrets.

Layering rules:

- Telegram handlers remain thin and call services only.
- Services do not import concrete Google API or Telegram SDK clients.
- Sheets gateway owns all business-data reads/writes.
- SQLite repository owns technical dialog-state persistence only.
- Notification router remains the only path for technical admin error messages.

### Shared resources

| Resource | Owner (creates) | Consumers | Instance count |
|----------|----------------|-----------|----------------|
| Google Sheets gateway boundary/fake | application composition or tests | participant flow service | 1 per process/test |
| Main bot client boundary/fake | application composition or tests | participant flow service | 1 configured boundary |
| Notification router | application composition or tests | participant flow service | 1 configured router |
| SQLite connection factory/path | application composition or tests | dialog state repository | many short-lived connections or one injected test DB |

## Decisions

### Decision 1: Adapter-independent service-level flows
**Decision:** Implement participant core flows as services and boundary methods, not as live Telegram SDK handlers.  
**Rationale:** Supports user-spec requirements that tests run without production Telegram token or Google credentials and that production deploy is out of scope.  
**Alternatives considered:** Add a real Telegram SDK adapter now. Rejected because the user-spec requires core behavior, not live runtime wiring, and adding live SDK setup would expand the feature beyond local verification.

### Decision 2: Google Sheets remains the identity and business-data source
**Decision:** Resolve Telegram IDs, consent, goals, planned steps, and weekly progress history through `SheetsGateway`.  
**Rationale:** Supports user-spec requirements that `/start` identifies users through Google Sheets and final business facts remain in Google Sheets.  
**Alternatives considered:** Cache participants/goals in SQLite. Rejected because SQLite must not become business storage.

### Decision 3: Re-check identity and consent on every protected action
**Decision:** Goal, steps, progress, insight placeholder, and captain placeholder actions resolve the current Telegram ID and require consent before returning data.  
**Rationale:** Supports user-spec requirements that participants do not see other participants' data and no data is shown before consent.  
**Alternatives considered:** Trust previously stored dialog state only. Rejected because SQLite state is technical and can be stale.

### Decision 4: Planned-step progress is calculated locally from Sheets rows
**Decision:** Compute progress percent and 6-cell progress bar from the current participant's planned steps, treating `closed` as complete and other statuses as not complete for the primary bar.  
**Rationale:** Supports user-spec requirement that progress display uses planned steps as the main progress source and separates weekly status history.  
**Alternatives considered:** Use weekly report scores as the primary progress percent. Rejected because user-spec explicitly separates weekly history from planned-step progress.

### Decision 5: Missing data uses safe participant copy plus technical admin notification
**Decision:** For missing `team_id`, active goal, or planned steps, return a neutral participant message and route details only to admin error chat.  
**Rationale:** Supports user-spec missing-data handling and project security rules for error notifications.  
**Alternatives considered:** Show raw missing fields to users. Rejected because it exposes internal schema details and creates poor Telegram UX.

### Decision 6: Out-of-scope menu actions are visible but inert
**Decision:** `💡 Мои инсайты` and captain-only menu buttons may be rendered, but they return short not-yet-available messages and do not write business facts.  
**Rationale:** Supports user-spec role-aware menus while preserving exclusions for insight submission, captain manual report, team report, scheduler, and PDF.  
**Alternatives considered:** Hide not-yet-implemented buttons. Rejected because approved scenarios define the role menus for this layer.

### Decision 7: SQLite stores only current technical flow state
**Decision:** Add a repository for `dialog_states` upsert/read/clear around current flow state; do not add new SQLite business tables.  
**Rationale:** Supports user-spec requirement that SQLite is used only for technical dialog/menu/consent state if needed.  
**Alternatives considered:** Add local participant/goal tables for faster views. Rejected because it violates storage boundaries.

## Data Models

### Python domain models

- `TelegramUserContext`: `telegram_id`, `chat_id`, optional `username`, optional `first_name`, optional `last_name`.
- `Participant`: `participant_id`, `telegram_id`, `username`, `full_name`, `role`, `team_id`, `team_name`, `captain_id`, `tracker_id`, `status`, `consent_given`, `consent_given_at`.
- `Goal`: `goal_id`, `participant_id`, `goal_title`, `goal_description`, `goal_value_amount`, `goal_value_currency`, `permission_condition`, `goal_status`.
- `PlannedStep`: `step_id`, `participant_id`, `goal_id`, `step_number`, `step_title`, `step_description`, `step_status`, `closed_week_number`, `closed_at`.
- `WeeklyStatus`: `week_number`, `status_symbol`, `status_code`, `submitted_at`.
- `MenuItem`: stable `action`, Russian `label`.
- `FlowResponse`: target `chat_id`, Russian `text`, optional `menu_items`, optional `buttons`.

### Sheets gateway extensions

`SheetsGateway` gains methods:

- `find_participant_by_telegram_id(telegram_id: int) -> SheetRow | None`
- `update_participant_consent(participant_id: str, *, consent_given: bool, consent_given_at: str) -> None`
- `get_active_goal(participant_id: str) -> SheetRow | None`
- `list_planned_steps(participant_id: str, goal_id: str) -> list[SheetRow]`
- `list_weekly_status_history(participant_id: str) -> list[SheetRow]`

The fake gateway stores rows in memory and returns defensive copies.

### SQLite technical state

Use existing `dialog_states` table. No schema migration is required unless tests uncover a missing technical flow value. The repository writes:

- `telegram_id`
- `participant_id`
- `role`
- `flow`: `consent`, `view_goal`, `view_steps`, `view_progress`, or `idle`
- `step`
- `started_at`
- `updated_at`
- `expires_at` when relevant

No participant, goal, planned-step, weekly-report, or insight business facts are persisted to SQLite.

## Dependencies

### New packages

None.

### Using existing (from project)

- `app.bot.clients` — main/error/notification bot boundaries and fake clients.
- `app.services.notifications` — technical error routing to error bot.
- `app.sheets.gateway` — Sheets gateway protocol and fake implementation.
- `app.storage.sqlite` — existing `dialog_states` schema.
- `tests/` — pytest unit and integration tests.
- `docs/04_google_sheets_schema.md` — source columns and allowed values.
- `docs/06_telegram_scenarios.md` — approved Telegram copy and menu contents.

## Testing Strategy

**Feature size:** M

### Unit tests

- Menu builder returns participant menu for `participant`.
- Menu builder returns participant plus captain buttons for `captain`.
- Progress formatter renders a 6-cell planned-step progress bar and percent.
- Message templates contain approved unknown-user and consent copy.
- Missing-data formatter does not include secrets or raw credentials.
- Sheets fake returns defensive copies and updates consent by participant ID.

### Integration tests

- `/start` for unknown Telegram ID sends approved user message and exactly one technical error notification through error bot.
- `/start` for known user without consent sends consent text/button and does not show menu.
- Consent acceptance writes consent through Sheets and then shows role-aware menu.
- `/start` for known user with existing consent shows role-aware menu immediately.
- Participant menu actions cannot return data before consent.
- Goal view reads only the current participant's active goal.
- Planned-steps view reads only the current participant's steps and is read-only.
- Progress view calculates progress from current participant planned steps and includes weekly history only as secondary information.
- Missing `team_id`, active goal, or planned steps produces safe participant text plus admin technical notification.
- Out-of-scope buttons do not create weekly reports, insights, voice records, PDFs, scheduler jobs, or deploy artifacts.

### E2E tests

None for this feature. Live Telegram bot and live Google Sheets verification are out of scope and require production-like secrets and separate approval.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Agent verifies the feature locally with pytest and focused integration tests using fake Sheets, fake Telegram bot clients, and a temporary SQLite database. No live Telegram MCP, Google API call, production deploy, or direct server action is required.

### Tools required

- bash
- pytest
- python local commands

## Risks

| Risk | Mitigation |
|------|-----------|
| Feature expands into weekly reports, insights, voice, PDF, or scheduler | Keep out-of-scope actions inert and add tests that no such business writes or dependencies are introduced. |
| Handlers or services bypass Sheets boundary | Service tests use gateway fakes, and implementation tasks keep handlers thin. |
| SQLite becomes a participant cache | Do not add business tables; repository only writes `dialog_states`. |
| Participant sees another participant's data | Re-resolve Telegram ID on protected actions and filter all reads by current participant ID. |
| Technical notifications leak personal data or secrets | Format admin errors with event type, Telegram ID, username, participant ID if known, and no token/credential values. |
| Progress calculation conflicts with weekly status history | Planned-step progress is primary; weekly history is rendered as secondary text only. |

## User-Spec Deviations

None

## Acceptance Criteria

- [ ] `/start` resolves Telegram ID through `SheetsGateway`, not SQLite.
- [ ] Unknown Telegram ID receives the approved Russian not-in-base message.
- [ ] Unknown-user technical notification is routed only through error bot.
- [ ] Known user without consent receives approved consent text and `✅ Согласен`.
- [ ] No menu or participant business data is shown before consent.
- [ ] Consent acceptance writes `consent_given` and `consent_given_at` through Sheets gateway.
- [ ] Known user with stored consent receives role-aware menu immediately.
- [ ] Participant and captain menus match approved Telegram scenarios.
- [ ] Protected actions re-resolve the current Telegram ID and scope reads to current participant.
- [ ] Goal view shows only the current participant's active goal fields.
- [ ] Planned-steps view is read-only and shows current participant steps.
- [ ] Progress view shows a 6-cell planned-step progress bar, percent, and optional secondary weekly history.
- [ ] Missing required data never crashes the flow and sends safe admin error notification.
- [ ] SQLite stores only technical dialog state for this feature.
- [ ] No live Telegram SDK, live Google API SDK, Docker, PostgreSQL, Redis, Celery, Kubernetes, PDF generation, voice processing, scheduler implementation, production deploy, weekly-report submission, or insight submission is added.
- [ ] Full pytest suite passes without production Telegram token or Google credentials.

## Implementation Tasks

### Wave 1 (independent)

#### Task 1: Participant domain and message contracts
- **Description:** Add typed domain objects, menu action constants, Russian message templates, and view formatters for participant core flows. This gives the service layer stable contracts and keeps user-facing copy centralized.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/bot/messages.py`, `app/bot/menus.py`, `app/services/participant_models.py`, `tests/test_participant_messages.py`
- **Files to read:** `docs/06_telegram_scenarios.md`, `work/participant-core-flows/user-spec.md`, `app/bot/clients.py`

#### Task 2: Participant Sheets boundary
- **Description:** Extend the Google Sheets gateway protocol and fake implementation for participant identity, consent, active goal, planned steps, and weekly status history. This keeps all business facts behind the approved Sheets boundary.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/sheets/gateway.py`, `tests/test_participant_sheets_gateway.py`
- **Files to read:** `docs/04_google_sheets_schema.md`, `work/participant-core-flows/user-spec.md`

#### Task 3: SQLite dialog state repository
- **Description:** Add a small repository for current dialog/menu technical state using the existing `dialog_states` table. This supports consent/menu flow persistence without creating business storage in SQLite.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/storage/dialog_state.py`, `tests/test_dialog_state_repository.py`
- **Files to read:** `app/storage/sqlite.py`, `docs/05_sqlite_state_schema.md`, `work/participant-core-flows/user-spec.md`

### Wave 2 (depends on Wave 1)

#### Task 4: Participant start and consent service
- **Description:** Implement `/start` and consent acceptance orchestration with Sheets lookup, dialog-state writes, main-bot replies, and error-bot routing for unknown users. This creates the safe entry point before any read-only participant data is exposed.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/services/participant_flows.py`, `tests/test_participant_start_flow.py`
- **Files to read:** `app/services/notifications.py`, `app/bot/clients.py`, `app/sheets/gateway.py`, `app/storage/dialog_state.py`, `work/participant-core-flows/user-spec.md`

#### Task 5: Read-only participant views
- **Description:** Implement goal, planned-steps, progress, and inert out-of-scope menu action handling for known consenting users. This gives participants useful read-only access while preserving scope boundaries.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/services/participant_flows.py`, `tests/test_participant_views.py`
- **Files to read:** `app/bot/messages.py`, `app/bot/menus.py`, `app/sheets/gateway.py`, `work/participant-core-flows/user-spec.md`

### Wave 3 (depends on Wave 2)

#### Task 6: Boundary and regression tests
- **Description:** Add cross-flow tests for participant scoping, missing-data notifications, consent-before-data rules, and out-of-scope exclusions. This locks the core safety guarantees before audit.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest -v` -> all tests pass without production secrets
- **Files to modify:** `tests/test_participant_boundaries.py`, existing participant flow tests as needed
- **Files to read:** `work/participant-core-flows/user-spec.md`, `work/participant-core-flows/tech-spec.md`, `tests/test_boundaries.py`

### Audit Wave

#### Task 7: Code Audit
- **Description:** Full-feature code quality audit. Read all source files created/modified in this feature and review architecture, naming, complexity, error handling, and boundary consistency.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 8: Security Audit
- **Description:** Full-feature security audit. Review consent enforcement, role/data scoping, technical error notifications, secret handling, and Google Sheets/SQLite boundary safety.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 9: Test Audit
- **Description:** Full-feature test quality audit. Review whether unit and integration tests meaningfully cover user-spec and tech-spec acceptance criteria without relying on production secrets.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 10: Pre-deploy QA
- **Description:** Acceptance testing for participant core flows: run all tests and verify user-spec plus tech-spec acceptance criteria. No deploy or post-deploy verification is included because production deploy is out of scope for this feature.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
