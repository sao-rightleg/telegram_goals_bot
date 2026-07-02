# Code Research: insight-flow

## Scope

Research for the personal participant insight flow after `weekly-report-flow`.

Confirmed product direction:

- Participant opens `💡 Мои инсайты`.
- Participant can add and list only their own insights.
- Captain uses this feature only for personal insights, not team insights.
- Insight records must be bound to date and challenge week for weekly summaries.
- Real voice transcription is deferred to a later shared `voice-processing` feature.

## Existing Code Touchpoints

### Telegram menu and participant flow

- `app/bot/menus.py`
  - `MenuAction.VIEW_INSIGHTS = "view_insights"` already exists.
  - Participant and captain menus already include `💡 Мои инсайты`.
- `app/services/participant_flows.py`
  - `VIEW_INSIGHTS` is currently in inert actions and returns `NOT_AVAILABLE_TEXT`.
  - Insight implementation should either route this action to a new `InsightService` or remove it from inert actions and let handlers call the insight service directly.
- `app/bot/messages.py`
  - Central Russian copy lives here.
  - Weekly report copy and formatters are good local style examples.

### Google Sheets boundary

- `app/sheets/gateway.py`
  - `SheetsGateway.append_insight(row)` already exists.
  - `SheetsGateway.list_insights()` currently returns all insight rows for tests/future readers.
  - `FakeSheetsGateway` stores `_insights` in memory and returns copies.
  - Needed for insight-flow:
    - scoped listing by participant, likely `list_insights_for_participant(participant_id)`.
    - full insight lookup with participant scoping, likely `get_insight(participant_id, insight_id)`.
    - optional duplicate/ID handling if service generates deterministic IDs.

### SQLite technical state

- `app/storage/sqlite.py`
  - `draft_sessions` already allows `draft_type = 'insight'`.
  - `dialog_states.flow` already allows `insight`.
  - `draft_messages` can preserve text/voice transcription order.
  - `draft_attachments` is ready for future voice-processing attachment data.
  - `draft_insights` exists with:
    - `draft_id`
    - `participant_id`
    - `goal_id`
    - `week_number`
    - `insight_scope`
    - `created_by_id`
    - `created_by_role`
    - timestamps
  - There is no repository for insight drafts yet.
- `app/storage/weekly_report_drafts.py`
  - Good implementation pattern for a future `InsightDraftRepository`.
  - It uses `draft_sessions`, `dialog_states`, `draft_messages`, clears previous active draft for the Telegram ID, and preserves message order.

### Calendar

- `app/scheduler/calendar.py`
  - `current_challenge_week_number(now)` can bind current-week insights to the shared challenge week.
  - It clamps week numbers to `1..8`.
  - There is no helper for previous-week scope, but service can derive `max(1, current_week - 1)` unless tech-spec chooses stricter behavior for week 1.

### Existing tests and boundary expectations

- `tests/test_participant_views.py`
  - `test_out_of_scope_actions_are_inert` currently asserts `VIEW_INSIGHTS` returns `NOT_AVAILABLE_TEXT` and creates no insight. This test must change when insight-flow is implemented.
- `tests/test_boundaries.py`
  - Confirms fake gateway insight behavior requires no credentials.
- `tests/test_weekly_report_sheets_gateway.py`
  - Confirms existing insight append/list fake behavior is preserved.
- `tests/test_weekly_report_draft_repository.py`
  - Good pattern for future `tests/test_insight_draft_repository.py`.

## Schema Notes

Approved `docs/04_google_sheets_schema.md` defines `Insights` columns:

- `insight_id`
- `participant_id`
- `goal_id`
- `week_number`
- `insight_scope`
- `insight_text`
- `transcription_text`
- `audio_file_path`
- `audio_deleted_at`
- `created_by_id`
- `created_by_role`
- `created_at`

Product discussion now requires a short insight title shown in the list and a user-facing insight date. The current schema has no `insight_title` or `insight_date` columns. User-spec/tech-spec must explicitly decide one of:

- add `insight_title` and `insight_date` to `Insights`, or
- store title/date only in `insight_text`/`created_at`, which is less clean and not recommended.

Decision from the interview: add both `insight_title` and `insight_date` to `Insights`.

## Likely New Modules

- `app/services/insight_models.py`
  - Insight scope enum/details.
  - Insight list item/page response models if needed.
- `app/storage/insight_drafts.py`
  - Create draft.
  - Set scope/week.
  - Append text message.
  - Set optional title.
  - Read active draft.
  - Clear draft.
- `app/services/insights.py`
  - Resolve participant by Telegram ID.
  - Enforce consent.
  - Enforce participant scoping.
  - Start add/list flows.
  - Save final insight to Sheets.
  - Format pagination and full-text callbacks at service boundary.

## Testing Strategy

Use fake Sheets and temp SQLite only.

Recommended tests:

- Message/copy tests for insight buttons, prompts, empty draft, success, list item formatting, and full-text view.
- Gateway tests for scoped participant insight listing and full insight lookup.
- Draft repository tests mirroring weekly report drafts:
  - create insight draft writes only technical state.
  - text messages preserve order.
  - title can be set/skipped.
  - clear removes draft/session/messages.
  - repository does not create business-primary tables.
- Service tests:
  - unknown user receives approved unknown-user copy and admin technical error.
  - no consent blocks insight data.
  - participant can add text insight and save final row with date/week/scope/title/text.
  - empty finalization creates no final insight and asks to repeat.
  - captain sees/adds only own insights.
  - participant cannot open another participant's insight full text.
  - list shows latest 10 first and paginates older/newer.
  - insight save does not create weekly report, weekly report step, planned-step closure, status, score, scheduler, PDF, or voice facts.

No live Telegram SDK, live Google API adapter, transcription provider, scheduler job, PDF generation, deploy, or production action is needed for this feature.

## Risks

- Title field is not in current Google Sheets schema. This must be handled explicitly before implementation.
- `читать целиком` must be implemented as a Telegram callback/inline action, not a public URL.
- Voice compatibility should not accidentally introduce real voice SDK/provider work in this feature.
- Listing all insights in one chat message can become noisy; pagination should remain part of acceptance criteria.
