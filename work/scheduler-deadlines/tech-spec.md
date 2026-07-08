---
created: 2026-07-08
status: draft
branch: dev
size: M
---

# Tech Spec: scheduler-deadlines

## Solution

Implement a local, adapter-independent scheduler execution slice around the existing calendar and storage foundations.

The feature adds:

- Scheduler reminder message copy and formatting.
- Sheets gateway queries needed to select reminder recipients, silent participants, teams, captains, and trackers.
- SQLite scheduler repositories for job runs, reminder logs, retry state, and technical errors.
- Scheduler service methods for reminder jobs and week close.
- Idempotent gray no-answer weekly report creation in Google Sheets.
- Aggregated silent participant notification routing for captains and trackers.
- Local pytest coverage with fake Sheets, fake bot clients, fake notification routing, and temporary SQLite.

No live Telegram polling, no live Google API adapter, no PDF/report generation, and no production deploy are included in this feature.

## Architecture

### What we're building/modifying

- **`app/bot/messages.py`** — add Russian scheduler reminder and silent participant notification formatters.
- **`app/sheets/gateway.py`** — extend the protocol and fake gateway with read methods required by scheduler jobs and idempotent gray report support.
- **`app/storage/scheduler.py`** — add SQLite repository for scheduler job runs, reminder attempts, retry state, and technical error recording.
- **`app/scheduler/jobs.py`** — add scheduler service/job execution logic for reminders and week close.
- **`app/scheduler/__init__.py`** — export scheduler service types where useful.
- **`tests/test_scheduler_deadlines.py`** — add local fake-boundary tests for reminder selection, retries, week close, gray creation, and silent notifications.
- **Existing tests** — keep weekly report, captain, SQLite schema, and scheduler foundation tests green.

### How it works

Reminder job flow:

1. Caller invokes `SchedulerService.run_reminder(reminder_type, now=...)`.
2. Service calculates current challenge week using `current_challenge_week_number(now)` and requires `Asia/Yekaterinburg` semantics from `app/scheduler/calendar.py`.
3. Service asks `SheetsGateway` for active participants eligible for reminders.
4. Service filters out:
   - dropped participants,
   - participants without consent,
   - participants that already have a weekly report for the current week,
   - participants missing a usable Telegram chat id.
5. Service formats the approved reminder text for the reminder type.
6. Service sends participant messages through the main bot path via `NotificationRouter` / `NotificationCategory.PARTICIPANT_MESSAGE`.
7. Each participant send is isolated. A failed participant send does not fail the whole reminder job.
8. Failed participant send is retried up to 3 times for that reminder job.
9. After retry exhaustion, service records failed/skipped state in SQLite and sends an admin technical error through error bot.
10. Service records sent/skipped/failed reminder state in SQLite so the same reminder job does not duplicate successful sends.

Week close flow:

1. Caller invokes `SchedulerService.close_week(now=...)` at or after Sunday 23:59 Yekaterinburg time.
2. Service calculates week number and loads active participants.
3. Service skips dropped participants.
4. For each active participant, service checks `SheetsGateway.find_weekly_report(participant_id, week_number=...)`.
5. If a weekly report already exists, service does nothing for that participant.
6. If no weekly report exists, service appends a gray weekly report row:
   - `status_code = "gray"`
   - `status_symbol = "⬜"`
   - score/status score = `0`
   - `submitted_by_role = "system"`
   - submitted source = `system_deadline`
   - empty report/transcription/audio fields
7. Unfinished drafts in SQLite are not cleared and do not affect week close.
8. Service groups newly silent participants by team and sends one operational notification to the captain and one to the tracker.
9. Missing captain/tracker chat id does not block gray report creation. Service skips that recipient and sends admin technical error.
10. Re-running week close is idempotent because existing participant/week weekly reports are checked before append.

### Shared resources

No heavy shared resources are introduced.

| Resource | Owner (creates) | Consumers | Instance count |
|----------|----------------|-----------|----------------|
| SQLite connection per operation | Scheduler repositories | Scheduler service | Per repository operation |
| Existing bot clients | Application composition / tests | NotificationRouter, SchedulerService | 3 existing bot clients |
| Existing Sheets gateway | Application composition / tests | SchedulerService | 1 gateway instance per composed service |

## Decisions

### Decision 1: Week close writes gray rows to Google Sheets
**Decision:** Scheduler creates official `gray` / `⬜` weekly report rows in Google Sheets during week close.
**Rationale:** Supports user-spec AC: `⬜` must become an official fact at Sunday 23:59, not a report-time calculation.
**Alternatives considered:** Calculate missing reports dynamically in future report generation. Rejected because it makes reports depend on each reader's logic and weakens idempotency.

### Decision 2: Week close is caller-idempotent
**Decision:** Before appending a gray row, scheduler checks whether the participant already has a weekly report for the same week.
**Rationale:** Supports user-spec AC: repeated week close must not duplicate weekly reports and must continue after partial Google Sheets failures.
**Alternatives considered:** Rely only on Google Sheets uniqueness. Rejected because current fake gateway and Sheets boundary do not enforce append uniqueness.

### Decision 3: Reminder retry is participant-scoped
**Decision:** Failed reminder sends are retried up to 3 times per participant per reminder job; failures do not block other participants.
**Rationale:** Supports user-spec AC: one bad Telegram recipient must not stop a team-wide reminder job.
**Alternatives considered:** Fail the whole job and rerun later. Rejected because it duplicates successful sends or delays unaffected participants.

### Decision 4: SQLite stores scheduler technical state only
**Decision:** SQLite repositories store job runs, reminder logs, retry attempts, and technical errors; Google Sheets stores final weekly report facts.
**Rationale:** Supports user-spec constraints and project storage boundary.
**Alternatives considered:** Store gray weekly reports in SQLite and export later. Rejected because SQLite must not be the only source for final business facts.

### Decision 5: Scheduler uses gateway methods rather than direct sheet rows
**Decision:** Scheduler depends on explicit `SheetsGateway` methods for active participants, teams, trackers, report lookup, and report append.
**Rationale:** Supports user-spec constraints and existing architecture: business logic must not know Google API details.
**Alternatives considered:** Read raw fake gateway internals or future Google worksheet APIs directly. Rejected because it breaks the integration boundary.

### Decision 6: No live adapter or deploy in this feature
**Decision:** Implement local scheduler services and fake-boundary tests only.
**Rationale:** Supports user-spec scope: live Telegram/test Google Sheets smoke is deferred to pre-deploy/deployment integration.
**Alternatives considered:** Add APScheduler/systemd/live Telegram smoke now. Rejected because production runtime is a separate MVP deployment-preparation phase.

### Decision 7: Use `status_score` at schema boundary and preserve existing `score` compatibility
**Decision:** Scheduler gray row construction should include the approved Google Sheets field semantics (`status_score = 0`) and keep existing test/fake compatibility where current code expects `score`.
**Rationale:** [TECHNICAL] `docs/04_google_sheets_schema.md` defines `status_score`, while existing services/tests currently use `score`. The tech-spec must avoid silently changing existing behavior while keeping future sheet mapping explicit.
**Alternatives considered:** Rename all existing service writes from `score` to `status_score` in this feature. Rejected as out-of-scope churn that would touch weekly/captain flows unrelated to scheduler.

## Data Models

### SheetsGateway protocol additions

Add scheduler-oriented protocol methods with fake implementation:

```python
def list_participants(self) -> list[SheetRow]:
    """Return all participant rows for scheduler selection."""

def list_teams(self) -> list[SheetRow]:
    """Return team rows used to resolve captain/tracker recipients."""

def get_tracker(self, tracker_id: str) -> SheetRow | None:
    """Return one tracker row by stable tracker_id."""
```

The scheduler can derive captain rows via existing `get_participant(captain_id)` and team members via existing `list_participants_by_team(team_id)`.

Expected participant/team/tracker fields used by scheduler:

- Participants: `participant_id`, `telegram_id`, `full_name`, `team_id`, `captain_id`, `tracker_id`, `status`, `consent_given`.
- Teams: `team_id`, `team_name`, `captain_id`, `tracker_id`, `is_active`.
- Trackers: `tracker_id`, `telegram_id`, `full_name`, `is_active`.
- WeeklyReports: `weekly_report_id`, `participant_id`, `team_id`, `goal_id`, `week_number`, `status_code`, `status_symbol`, `score`/`status_score`, `report_text`, `transcription_text`, `audio_file_path`, `audio_deleted_at`, `submitted_at`, `submitted_by_id`, `submitted_by_role`, `flow_source`/`submitted_source`.

### Gray report row

Scheduler-created gray row:

```python
{
    "weekly_report_id": f"WR:{participant_id}:week-{week_number:02d}",
    "participant_id": participant_id,
    "team_id": team_id,
    "goal_id": active_goal_id_or_empty,
    "week_number": week_number,
    "status_code": "gray",
    "status_symbol": "⬜",
    "score": 0,
    "status_score": 0,
    "report_text": "",
    "transcription_text": "",
    "audio_file_path": "",
    "audio_deleted_at": "",
    "submitted_at": now.isoformat(),
    "submitted_by_id": "system",
    "submitted_by_role": "system",
    "flow_source": "system_deadline",
    "submitted_source": "system_deadline",
}
```

If active goal is missing, scheduler still creates the gray row with `goal_id = ""` and sends admin error. Reason: no-answer status is tied to weekly participation and must not be skipped because profile data is incomplete.

### Scheduler repository

Add `app/storage/scheduler.py` with:

- `SchedulerJobRepository`
  - `start_job_run(job_type, week_number, scheduled_for, idempotency_key, started_at)`
  - `finish_job_run(job_run_id, status, finished_at, error_message=None)`
  - `has_successful_reminder(participant_id, week_number, reminder_type)`
  - `record_reminder_attempt(participant_id, team_id, week_number, reminder_type, sent_at, status, telegram_message_id=None, error_message=None)`
  - `record_error(module, error_type, severity, message, created_at, participant_id=None, team_id=None, admin_notified=False)`

Current `reminder_log` has a unique participant/week/reminder row. To support retries without schema churn, repository should upsert that row and store the latest status/error. If task implementation finds attempt count cannot be represented cleanly, add `attempt_count INTEGER NOT NULL DEFAULT 0` to `reminder_log` through `app/storage/sqlite.py` and update schema tests. This is allowed technical-state evolution, not a business-schema change.

### Scheduler service models

Add lightweight dataclasses in `app/scheduler/jobs.py` or `app/scheduler/models.py` if needed:

- `ReminderJobResult(sent_count, skipped_count, failed_count)`
- `WeekCloseResult(gray_created_count, existing_count, failed_count, notified_team_count)`
- `SilentParticipant(participant_id, team_id, full_name)`

## Dependencies

### New packages

None.

### Using existing (from project)

- `app/scheduler/calendar.py` — timezone, challenge week, reminder schedule, idempotency keys.
- `app/sheets/gateway.py` — business fact reads/writes through fake/local boundary.
- `app/services/notifications.py` — main/error/notification bot routing.
- `app/bot/clients.py` — bot protocol and fake clients.
- `app/bot/messages.py` — Russian copy and formatters.
- `app/storage/sqlite.py` — existing scheduler, reminder, job run, and error tables.
- `app/services/weekly_report_models.py` — existing status code/symbol/score conventions.

## Testing Strategy

**Feature size:** M

### Unit tests

- Reminder copy formatters for each scheduler reminder type.
- Silent participant notification formatter.
- Reminder recipient filtering:
  - active + consent + no report -> included,
  - no consent -> excluded from reminders,
  - dropped -> excluded,
  - already reported -> excluded.
- Week close participant filtering:
  - active + no report -> gray created,
  - active + no consent + no report -> gray created,
  - dropped -> skipped,
  - already reported -> skipped.
- Gray report row fields and status values.
- Retry cap: max 3 attempts for a failed participant recipient.

### Integration tests

- Reminder job with fake Sheets, fake main bot, fake error bot, and SQLite temp database sends expected messages and records reminder state.
- Failed send for one participant retries only that participant and does not block other sends.
- Week close creates gray rows for only missing active participants.
- Re-running week close does not create duplicate gray rows.
- Simulated partial Sheets failure followed by rerun creates only missing gray rows.
- Aggregated silent notifications go to captain/tracker recipients for the correct team only.
- Missing captain/tracker chat id triggers admin error and does not block week close.
- Existing weekly report late/finalization tests remain green.

### E2E tests

None for this feature. Live Telegram and test Google Sheets smoke is deferred to a later deployment/pre-deploy integration feature.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Automated verification is local pytest-first. The implementation task should run targeted scheduler tests while developing, then the final QA task runs the full test suite. No live Telegram bot, live Google Sheets, browser, or production service check is required for this feature.

### Tools required

- bash / pytest
- Python import/smoke commands

No Playwright MCP, Telegram MCP, curl, Docker, or external API tools are required.

## Risks

| Risk | Mitigation |
|------|-----------|
| Duplicate gray reports after rerun | Check existing participant/week weekly report before append and cover reruns in tests. |
| Partial Google Sheets failure leaves missing rows | Rerun week close idempotently and test failure-then-rerun behavior. |
| Reminder send failure blocks all recipients | Isolate per participant, retry capped at 3 attempts, record failed state and admin error. |
| Cross-team privacy leak in silent notifications | Group by team and resolve captain/tracker from team scope; test separate teams. |
| Retry state does not fit current SQLite schema | Add minimal technical column/repository behavior in `reminder_log`; keep final facts in Google Sheets. |
| Field mismatch between docs and current fake rows (`status_score` vs `score`) | Include both keys for scheduler-created rows and document future mapper responsibility. |

## User-Spec Deviations

None.

## Acceptance Criteria

Technical acceptance criteria complement the user-facing criteria from `user-spec.md`:

- [ ] `tech-spec.md` scope does not include PDF/report generation, production deploy, APScheduler/systemd runtime, or live Google/Telegram adapters.
- [ ] Scheduler service uses `Asia/Yekaterinburg` calendar helpers and does not rely on VPS local timezone.
- [ ] Sheets access happens through `SheetsGateway`; scheduler does not call Google APIs directly.
- [ ] SQLite stores only technical scheduler/reminder/retry/error state.
- [ ] Final gray weekly report facts are written to Google Sheets gateway, not SQLite only.
- [ ] Reminder sends are participant-isolated and retry-capped at 3 attempts.
- [ ] Week close is idempotent across repeated runs and partial failure recovery.
- [ ] Silent notifications are team-scoped and role-safe.
- [ ] Missing recipient chat ids produce admin technical errors without blocking week close.
- [ ] All new tests and existing local test suite pass.
- [ ] No secrets, tokens, credentials, live chat ids, or generated files are committed.

## Implementation Tasks

### Wave 1 (independent foundations)

#### Task 1: Scheduler Copy and Result Contracts
- **Description:** Add Russian scheduler reminder and silent notification formatters plus small result/data contracts for scheduler jobs. This gives later service code stable copy and return values without embedding strings in job logic.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, test-reviewer
- **Files to modify:** `app/bot/messages.py`, `app/scheduler/jobs.py`, `tests/test_scheduler_messages.py`
- **Files to read:** `work/scheduler-deadlines/user-spec.md`, `app/bot/messages.py`, `tests/test_weekly_report_messages.py`

#### Task 2: Scheduler Sheets Gateway Queries
- **Description:** Extend `SheetsGateway` and `FakeSheetsGateway` with scheduler read paths for participants, teams, and trackers while preserving existing fake-boundary behavior. This enables scheduler services to select recipients and resolve captain/tracker notification targets without direct sheet internals.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/sheets/gateway.py`, `tests/test_scheduler_sheets_gateway.py`
- **Files to read:** `docs/04_google_sheets_schema.md`, `app/sheets/gateway.py`, `tests/test_participant_sheets_gateway.py`, `tests/test_weekly_report_sheets_gateway.py`

#### Task 3: Scheduler SQLite Repository
- **Description:** Add a repository for scheduler job runs, reminder records, retry state, and local technical errors. It should use existing scheduler tables where possible and add only minimal technical schema support if retry attempts cannot be represented cleanly.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/storage/scheduler.py`, `app/storage/sqlite.py`, `tests/test_scheduler_repository.py`, `tests/test_sqlite_schema.py`
- **Files to read:** `docs/05_sqlite_state_schema.md`, `app/storage/sqlite.py`, `tests/test_sqlite_schema.py`

### Wave 2 (depends on Wave 1)

#### Task 4: Reminder Job Service
- **Description:** Implement reminder job execution using scheduler calendar, Sheets recipient filtering, notification routing, SQLite reminder logging, and participant-scoped retry. Result: approved reminders are sent only to eligible participants and failures are isolated.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/scheduler/jobs.py`, `tests/test_scheduler_deadlines.py`
- **Files to read:** `app/scheduler/calendar.py`, `app/services/notifications.py`, `app/bot/clients.py`, `app/sheets/gateway.py`, `app/storage/scheduler.py`, `work/scheduler-deadlines/user-spec.md`

#### Task 5: Week Close Service
- **Description:** Implement idempotent week close that creates gray no-answer weekly reports for active participants without finalized reports. Result: repeated runs and partial failure recovery create only missing gray rows and preserve unfinished drafts.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/scheduler/jobs.py`, `tests/test_scheduler_deadlines.py`
- **Files to read:** `app/services/weekly_reports.py`, `app/services/captains.py`, `app/services/weekly_report_models.py`, `app/sheets/gateway.py`, `app/storage/weekly_report_drafts.py`

#### Task 6: Silent Participant Notifications
- **Description:** Add team-scoped captain/tracker silent participant notifications after week close. Result: each team gets aggregated operational notifications to authorized recipients, while missing recipient data produces admin errors without blocking gray creation.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/scheduler/jobs.py`, `tests/test_scheduler_deadlines.py`
- **Files to read:** `docs/07_reports.md`, `app/services/notifications.py`, `app/bot/messages.py`, `app/sheets/gateway.py`

### Wave 3 (integration hardening)

#### Task 7: Scheduler Boundary and Regression Coverage
- **Description:** Broaden local tests around scheduler edge cases and existing weekly-report deadline behavior. Result: scheduler behavior is covered with fake boundaries and existing participant/captain flows remain unchanged.
- **Skill:** test-master
- **Reviewers:** code-reviewer, test-reviewer
- **Verify-smoke:** `python -m pytest tests/test_scheduler_foundation.py tests/test_scheduler_deadlines.py tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py` → pass
- **Files to modify:** `tests/test_scheduler_deadlines.py`, `tests/test_weekly_report_finalize.py`, `tests/test_weekly_report_boundaries.py`
- **Files to read:** `work/scheduler-deadlines/user-spec.md`, `work/scheduler-deadlines/tech-spec.md`, `tests/test_scheduler_foundation.py`

### Audit Wave

#### Task 8: Code Audit
- **Description:** Full-feature code quality audit. Read all scheduler, Sheets gateway, SQLite repository, message formatter, and test files modified in this feature; review holistically for architecture and maintainability issues. Write audit report.
- **Skill:** code-reviewing
- **Reviewers:** none

#### Task 9: Security Audit
- **Description:** Full-feature security audit. Review role-safe notification routing, personal data in silent notifications, admin error content, retry logging, and storage boundaries. Write audit report.
- **Skill:** security-auditor
- **Reviewers:** none

#### Task 10: Test Audit
- **Description:** Full-feature test quality audit. Verify scheduler tests cover idempotency, retries, recipient filtering, partial failures, and privacy boundaries with meaningful assertions. Write audit report.
- **Skill:** test-master
- **Reviewers:** none

### Final Wave

#### Task 11: Pre-deploy QA
- **Description:** Run local acceptance testing for the scheduler-deadlines feature and verify user-spec and tech-spec acceptance criteria. No production deploy or live external service check is required for this feature.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `python -m pytest` → pass
- **Files to modify:** `work/scheduler-deadlines/logs/working/task-11/pre-deploy-qa.json`, `work/scheduler-deadlines/decisions.md`
- **Files to read:** `work/scheduler-deadlines/user-spec.md`, `work/scheduler-deadlines/tech-spec.md`, `tests/`
