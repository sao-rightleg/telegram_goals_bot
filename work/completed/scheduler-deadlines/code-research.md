# Code Research: scheduler-deadlines

## Scope

Feature scope confirmed by interview:

- Weekly reminder execution.
- Sunday 23:59 week close in `Asia/Yekaterinburg`.
- Official gray `⬜` weekly report creation for active participants without finalized reports.
- Aggregated silent participant notifications to captain and tracker.
- Participant-level retry for failed reminder sends.
- No PDF/report generation in this feature.

## Existing Code

### Calendar and job identity

- `app/scheduler/calendar.py`
  - Defines `TIMEZONE_NAME = "Asia/Yekaterinburg"`.
  - Defines challenge calendar constants and `current_challenge_week_number`.
  - Defines `weekly_report_deadline` and `is_weekly_report_open`.
  - Defines `reminder_schedule()` with approved reminder times:
    - `monday_reminder` Monday 10:00
    - `wednesday_checkin` Wednesday 10:00
    - `sunday_1800_checkin` Sunday 18:00
    - `sunday_2230_reminder` Sunday 22:30
    - `sunday_2300_reminder` Sunday 23:00
    - `week_close` Sunday 23:59
  - Defines `build_idempotency_key`.

### SQLite technical state

- `app/storage/sqlite.py`
  - Existing technical tables already include:
    - `scheduler_jobs`
    - `job_runs`
    - `reminder_log`
    - `error_events`
  - `scheduler_jobs` has `UNIQUE (job_type, week_number, scheduled_for)`.
  - `job_runs` has unique `idempotency_key`.
  - `reminder_log` has `UNIQUE (participant_id, week_number, reminder_type)`.
  - Current schema records reminder status but does not include attempt count. Tech-spec should decide whether retry attempts need a new repository/table shape or can be represented through job runs/error events.

### Weekly report service

- `app/services/weekly_reports.py`
  - Uses `current_challenge_week_number` and `is_weekly_report_open`.
  - Rejects late report finalization without saving final business facts.
  - Keeps active draft when late finalization is rejected.
  - Writes final weekly reports through `SheetsGateway.append_weekly_report`.
  - Checks duplicates through `SheetsGateway.find_weekly_report`.
  - Constructs weekly report ids as `WR:{participant_id}:week-{week_number:02d}`.
  - Gray/system no-answer report creation does not exist yet.

### Captain manual report service

- `app/services/captains.py`
  - Uses the same deadline and duplicate report rules.
  - Writes final reports with `submitted_by_role = captain`.
  - Rejects dropped participants for captain manual reports.
  - Useful pattern for scheduler to enforce dropped participant exclusion.

### Notification routing and bot boundaries

- `app/services/notifications.py`
  - `NotificationRouter.send` routes:
    - `PARTICIPANT_MESSAGE` through main bot.
    - `TECHNICAL_ERROR` through error bot to admin error chat.
    - Operational/report notifications through notification bot.
  - Current router sends to all recipients and does not model per-recipient failure/retry. Tech-spec should define whether scheduler catches `BotClient.send_message` exceptions around each recipient.

- `app/bot/clients.py`
  - `BotClient.send_message` protocol returns `OutgoingMessage`.
  - `FakeBotClient` records sent messages.

### Sheets boundary

- `app/sheets/gateway.py`
  - Existing protocol supports participant lookup by Telegram ID, participant lookup by participant ID, team-scoped participant listing, active goal lookup, planned steps listing, report append, duplicate report lookup, and final report readers.
  - Missing for scheduler:
    - List active participants globally or by team.
    - List teams/captains/trackers or resolve team recipients.
    - Possibly list participants by tracker/team grouping for notifications.
    - Optional append-idempotent weekly report or uniqueness handling for gray reports.
  - `FakeSheetsGateway.append_weekly_report` currently appends without duplicate guard. Existing services rely on caller-side `find_weekly_report`.

### Telegram copy

- `app/bot/messages.py`
  - Contains weekly report and captain copy.
  - Scheduler reminder copy does not exist yet.
  - User-approved silent participant notification copy:
    - `Нет отчёта за неделю {week_number}: {N} участник(ов).`
    - Followed by participant names.

## Existing Tests

- `tests/test_scheduler_foundation.py`
  - Verifies timezone, challenge dates, schedule constants, and idempotency key format.

- `tests/test_sqlite_schema.py`
  - Verifies scheduler/reminder schema idempotency constraints.

- Weekly report and captain tests verify:
  - Late reports do not save final facts.
  - Duplicate reports are rejected.
  - Final weekly reports are saved through fake Sheets.
  - Drafts remain when late/duplicate finalization is rejected.

## User Decisions From Interview

- Feature name: `scheduler-deadlines`.
- Sunday 18:00 is only a text reminder that the deadline is close, not a report-flow launch.
- Reminders go to active consenting participants without a finalized weekly report.
- Dropped participants do not receive normal reminders.
- Week close writes official gray `⬜` weekly report rows in Google Sheets for active participants without finalized reports.
- If a participant has an unfinished draft at deadline, they still become gray/silent; the draft remains as technical draft/history.
- Week close must be idempotent: repeated runs skip existing weekly reports and create only missing gray rows.
- Silent participant notifications are one aggregated message to the captain and tracker for the team.
- No extra participant-facing message after week close.
- Failed reminder send for one participant must not fail the whole job.
- Failed reminder send gets up to 3 attempts for that participant; after exhaustion, record failed/skipped in SQLite and notify admin.
- Later planned reminders may try again if the participant still has no report.
- Testing strategy: local pytest/fake boundaries plus manual service/job-runner smoke. Live Telegram/test Google Sheets smoke is deferred to deployment/pre-deploy integration unless live adapters are introduced.

## Main Integration Risks

- Current Sheets protocol does not expose all participant/team/tracker recipient queries scheduler needs.
- Retry state may need more explicit storage than current `reminder_log` columns provide.
- Duplicate gray rows must be prevented by caller logic and/or storage/gateway uniqueness assumptions.
- Notification routing currently does not expose partial send failure semantics; scheduler should isolate sends per participant/recipient.
- Silent participant notification must not leak data across teams/trackers.

## Recommended User-Spec Boundaries

- Specify behavior and acceptance criteria, not exact repository design.
- Keep PDF generation/report delivery out of scope.
- Require idempotent week close and participant-level reminder retry.
- Require fake-boundary tests for reminders, week close, duplicate prevention, dropped/consent exclusion, and notification routing.
