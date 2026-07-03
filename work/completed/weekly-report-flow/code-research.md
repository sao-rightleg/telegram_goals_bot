# Code Research: weekly-report-flow

## Current implemented base

The repository now has `participant-core-flows` implemented:

- `app/services/participant_flows.py` handles `/start`, consent, role-aware menu, read-only goal/steps/progress, missing-data notifications, and inert out-of-scope actions.
- `app/bot/messages.py` contains approved Russian copy and view formatters.
- `app/bot/menus.py` contains role-aware participant/captain menu actions.
- `app/sheets/gateway.py` exposes `SheetsGateway` and `FakeSheetsGateway` for participants, consent, active goal, planned steps, weekly status history, weekly report append, and insight append.
- `app/storage/dialog_state.py` can upsert/read/clear `dialog_states`.
- `app/storage/sqlite.py` already contains tables for `draft_sessions`, `draft_messages`, `draft_reports`, and related technical draft state.
- Tests currently pass: 73 tests.

## Relevant existing boundaries

- Google Sheets is still the business source of truth.
- SQLite is already prepared for weekly report draft metadata and draft messages, but no repository exists yet for draft sessions/messages/reports.
- `FakeSheetsGateway` can append weekly report rows, but does not yet support:
  - appending `WeeklyReportSteps` relations;
  - updating planned step status to `closed` or `partial`;
  - checking whether a participant already submitted a report for a week;
  - generating stable weekly report IDs.
- `ParticipantFlowService` currently treats weekly report and captain manual report actions as out of scope/inert.

## Implementation-level gaps for this feature

- No weekly report service or state machine.
- No status selection handling for green/blue/red.
- No selected planned-step storage/update helpers.
- No text draft message repository.
- No final save orchestration to append `WeeklyReports`, append `WeeklyReportSteps`, and update planned steps for green reports.
- No deadline guard for Sunday 23:59 Yekaterinburg.
- No duplicate weekly report guard.
- No tests for empty final report prevention.

## Suggested implementation direction for tech-spec

- Keep the first weekly report feature service-level and adapter-independent.
- Use fake Sheets and temporary SQLite for all tests.
- Add a weekly report service that can be called by a future Telegram adapter, scheduler reminder, or command handler.
- Support text messages only in this feature. Keep voice processing as a separate feature.
- Support participant-submitted green/blue/red before deadline.
- For green and blue, require one or more planned step IDs.
- For red, selected steps are not required.
- On final save:
  - append one WeeklyReports row;
  - append WeeklyReportSteps rows for selected steps when status is green or blue;
  - mark selected planned steps as `closed` for green;
  - do not mark final goal achieved automatically;
  - clear SQLite draft state.
- Keep no-answer gray status, reminders, scheduler, captain manual report, insights, PDF, live Telegram SDK, live Google API adapter, and deploy out of scope.
