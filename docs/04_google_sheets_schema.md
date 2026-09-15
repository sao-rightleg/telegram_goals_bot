# Google Sheets Schema

## Purpose

Google Sheets is the main business database for the MVP.

The schema must be simple enough for admin to manage manually and structured enough for reliable bot reads, writes, reports, and future migration if needed.

## Schema Principles

- Use separate sheets by entity.
- Use stable internal IDs.
- Do not use Telegram ID as the primary business ID.
- Use one row per entity.
- Avoid merged cells.
- Avoid multi-row headers.
- Store status codes as text, not only as colors or emojis.
- Keep critical data sheets free from complex formulas.
- Use Google Sheets for final business facts, not temporary dialogue state.

## ID Rules

Recommended ID examples:
- `flow_id`: `FLOW_TEST_2026_08`
- `participant_id`: `P001`
- `team_id`: `T001`
- `tracker_id`: `TR001`
- `goal_id`: `G001`
- `step_id`: `S001`
- `weekly_report_id`: `WR001`
- `insight_id`: `I001`
- `report_run_id`: `RR001`
- `error_id`: `E001`

## Sheets

The MVP uses two Google Sheets documents:
- Main business spreadsheet: participants, teams, goals, steps, reports, insights.
- Challenge flows spreadsheet: flow registry, launch calendar, flow-level counters, and day-by-day scheduled events.

## ChallengeFlows

Stores challenge flow launches and the active calendar in a separate Google Sheets document configured by `CHALLENGE_FLOWS_SHEETS_ID`.

Columns:
- `flow_id`
- `flow_name`
- `flow_status`
- `kickoff_meeting_at`
- `registration_opens_at`
- `registration_closes_at`
- `data_collection_due_at`
- `bot_invite_at`
- `challenge_start_date`
- `goal_setup_start_date`
- `goal_setup_end_date`
- `steps_setup_start_date`
- `steps_setup_end_date`
- `week_01_start_date`
- `week_08_end_date`
- `final_summary_start_date`
- `final_summary_end_date`
- `expected_participant_count`
- `actual_participant_count`
- `active_team_count`
- `created_at`
- `updated_at`

Allowed `flow_status` values:
- `planned`
- `active`
- `completed`
- `archived`

Notes:
- Only one flow should have `flow_status = active` at a time.
- Runtime uses `challenge_start_date` from the active flow.
- Working weeks are named `week_01` through `week_08`.
- `kickoff_meeting_at`, `registration_opens_at`, and `registration_closes_at` are timestamps in `Asia/Yekaterinburg`.
- `registration_opens_at` must equal `kickoff_meeting_at`.
- `registration_closes_at` must equal `registration_opens_at + 7 days`.
- The per-flow `FlowStart` sheet calculates both registration boundaries and includes them in launch-readiness validation.

## FlowSchedule

Stores the explicit event timeline for each challenge flow. One row represents one scheduled event.

Columns:
- `event_id`
- `flow_id`
- `day_offset`
- `scheduled_date`
- `scheduled_time`
- `scheduled_timezone`
- `weekday_code`
- `phase_code`
- `week_position`
- `event_type`
- `recipient_role`
- `week_number`
- `message_text`
- `condition_code`
- `is_enabled`
- `sort_order`
- `created_at`
- `updated_at`

Allowed `event_type` values:
- `participant_message`
- `weekly_focus_prompt`
- `weekly_checkin`
- `missing_report_reminder`
- `week_close`
- `silent_participant_notification`
- `report_generate`
- `report_send`
- `final_summary_message`

Allowed `recipient_role` values:
- `participant`
- `captain`
- `tracker`
- `admin`
- `sitnikov`
- `system`

Allowed `condition_code` values:
- `always`
- `consent_given`
- `weekly_report_missing`
- `weekly_report_submitted`
- `weekly_focus_missing`
- `silent_participants_exist`
- `reports_generated`

Rules:
- `event_id` is unique and stable.
- `flow_id` must reference `ChallengeFlows.flow_id`.
- `day_offset = 0` means the flow start date; `day_offset = 1` means the next calendar day.
- `scheduled_date` is the materialized calendar date in `YYYY-MM-DD`.
- `scheduled_time` uses `HH:MM` and `Asia/Yekaterinburg`.
- `scheduled_timezone` is required for every event and equals `Asia/Yekaterinburg` in the MVP.
- `weekday_code` is calculated from `scheduled_date`: `monday` through `sunday`.
- `phase_code` identifies `goal_setup`, `steps_setup`, `week_01` through `week_08`, or `final_summary`.
- `week_position` is `start`, `middle`, `end`, or empty for events outside a working week.
- `week_number` is required only for week-specific events.
- `message_text` is user-facing Russian text and may be empty for system-only events.
- `is_enabled` controls whether the event is eligible to run.
- The scheduler records execution state in SQLite and must not send the same event twice to the same recipient.
- Role resolution and report visibility remain enforced by application code; spreadsheet text cannot broaden access.
- Events may target only entities with the same `flow_id`.
- Before activation, every materialized date and weekday must be validated against the flow start date and `day_offset`.
- Runtime executes `scheduled_date` directly; it does not recalculate events from the current weekday.

## Participants

Stores all people who can interact with the bot.

Columns:
- `flow_id`
- `participant_id`
- `telegram_id`
- `username`
- `last_name`
- `first_name`
- `middle_name`
- `full_name`
- `gender`
- `role`
- `team_id`
- `team_name`
- `captain_id`
- `tracker_id`
- `status`
- `participant_stage`
- `drop_reason`
- `consent_given`
- `consent_given_at`
- `consent_status`
- `bot_started_at`
- `onboarding_completed_at`
- `last_stage_updated_at`
- `created_at`
- `updated_at`

Allowed `role` values:
- `participant`
- `captain`
- `tracker`
- `admin`
- `sitnikov`

Allowed `status` values:
- `active`
- `risk_zone`
- `dropped`

Notes:
- Captain is also a participant with role `captain`.
- Dropped status is managed manually through Google Sheets in MVP.
- Consent must be stored here or in a separate consent history sheet if later needed.
- `participant_stage` tracks where the participant currently is: `invited`, `onboarding`, `goal_setup`, `steps_setup`, `week_01` through `week_08`, `final_summary`, `completed`, or `declined`.
- `bot_started_at` is set when an expected participant first opens the bot.

## Teams

Stores teams.

Columns:
- `flow_id`
- `team_id`
- `team_name`
- `gender`
- `captain_id`
- `tracker_id`
- `is_active`
- `created_at`
- `updated_at`

Allowed `gender` values:
- `male`
- `female`

## Trackers

Stores tracker users and their team scope.

Columns:
- `tracker_id`
- `telegram_id`
- `full_name`
- `gender_scope`
- `role`
- `is_active`

Allowed `gender_scope` values:
- `male`
- `female`
- `all`

Current assignment:
- Ivan Larkin receives male team reports.
- Maria receives female team reports.

## Goals

Stores participant goals.

Columns:
- `goal_id`
- `participant_id`
- `goal_title`
- `goal_description`
- `goal_value_amount`
- `goal_value_currency`
- `permission_condition`
- `permission_metric_amount`
- `permission_metric_unit`
- `goal_status`
- `goal_achieved_by_id`
- `goal_achieved_by_role`
- `achieved_at`
- `created_at`
- `updated_at`

Allowed `goal_status` values:
- `active`
- `achieved`
- `paused`
- `cancelled`

Notes:
- Goal is a concrete desired object or result.
- Goal is not simply money.
- Final goal achievement is fixed by tracker.
- Admin may also fix final goal achievement through Google Sheets.
- Participant and captain cannot mark final goal as achieved.
- Bot must not automatically mark final goal as achieved only because all planned steps are closed.
- Allowed `goal_achieved_by_role` values: `tracker`, `admin`.

## PlannedSteps

Stores predefined participant steps.

Columns:
- `step_id`
- `participant_id`
- `goal_id`
- `step_number`
- `step_title`
- `step_description`
- `step_metric`
- `step_status`
- `closed_week_number`
- `closed_report_id`
- `closed_at`
- `created_at`
- `updated_at`

Allowed `step_status` values:
- `open`
- `partial`
- `closed`
- `cancelled`

Notes:
- Steps are not tied to specific weeks.
- Participants cannot add new steps in MVP.
- Main route contains 6 planned steps.
- One weekly report may close several steps.
- Already closed steps cannot be closed again.
- New/additional steps are formulated by participant with captain/tracker and added by admin in Google Sheets.

## WeeklyReports

Stores final weekly reports.

Columns:
- `weekly_report_id`
- `participant_id`
- `team_id`
- `goal_id`
- `week_number`
- `week_start_date`
- `week_end_date`
- `status_symbol`
- `status_code`
- `status_score`
- `report_text`
- `transcription_text`
- `audio_file_path`
- `audio_deleted_at`
- `submitted_by_id`
- `submitted_by_role`
- `submitted_source`
- `submitted_at`
- `is_before_deadline`
- `created_at`
- `updated_at`

Allowed `status_code` values:
- `green`
- `blue`
- `red`
- `gray`

Allowed `status_symbol` values:
- `🟩`
- `🟦`
- `🟥`
- `⬛`

Allowed `status_score` values:
- `1`
- `0.5`
- `0`

Allowed `submitted_by_role` values:
- `participant`
- `captain`
- `admin`
- `system`

Allowed `submitted_source` values:
- `participant_bot`
- `captain_manual`
- `system_deadline`

Rules:
- No yellow late status.
- Late reports after Sunday 23:59 Yekaterinburg time do not change weekly status.
- Missing report after deadline becomes `gray` / `⬛` from `system_deadline`.
- `⬜` is a computed UI placeholder for a current or future week and is not stored as a final weekly report status.
- Participant step reports are stored as one report per planned step.
- Participant step report IDs include participant, week, and step ID.
- `green` participant step reports must have exactly one related row in `WeeklyReportSteps`.
- Late report text may be stored, but `status_code`, `status_symbol`, and `status_score` for the closed week must not change.
- Audio file path remains in Google Sheets after audio deletion; use `audio_deleted_at` to indicate retention cleanup.

## WeeklyReportSteps

Stores relation between weekly reports and planned steps.

Columns:
- `id`
- `weekly_report_id`
- `participant_id`
- `step_id`
- `relation_type`
- `created_at`

Allowed `relation_type` values:
- `closed`
- `partial`
- `mentioned`

Notes:
- This sheet is mandatory for participant step reports.
- `green` participant step reports require one `closed` relation.
- A planned step can have only one final participant step report.
- Bot must reject duplicate closure of already closed steps.

## WeeklyFocus

Stores the mandatory weekly focus selected by participant.

Columns:
- `focus_id`
- `participant_id`
- `goal_id`
- `step_id`
- `week_number`
- `week_start_date`
- `week_end_date`
- `focus_status`
- `selected_at`
- `updated_at`

Allowed `focus_status` values:
- `active`
- `completed`
- `skipped`

Rules:
- Focus is mandatory when participant has open planned steps.
- Focus can be selected only from open planned steps.
- Focus cannot be changed inside the same week.
- Closing the focused step does not require selecting a new focus.
- Focus does not prevent reporting another step in the same week.
- Captains and trackers see weekly focus in reports.

## Insights

Stores insights separately from progress.

Columns:
- `insight_id`
- `participant_id`
- `goal_id`
- `week_number`
- `insight_scope`
- `insight_title`
- `insight_date`
- `insight_text`
- `transcription_text`
- `audio_file_path`
- `audio_deleted_at`
- `created_by_id`
- `created_by_role`
- `created_at`

Allowed `insight_scope` values:
- `current_week`
- `previous_week`
- `goal_general`

Allowed `created_by_role` values:
- `participant`
- `captain`
- `admin`

Rules:
- Insight does not count as victory.
- Insight does not change weekly status.
- Insight does not replace action.
- Audio file path remains after audio deletion; transcription text remains permanently.

## ReportRuns

Stores report generation and sending metadata.

Columns:
- `report_run_id`
- `week_number`
- `team_id`
- `report_type`
- `pdf_file_path`
- `pdf_expires_at`
- `generated_at`
- `sent_to_captain`
- `sent_to_tracker`
- `sent_to_admin`
- `sent_to_sitnikov`
- `status`
- `error_message`

Allowed `report_type` values:
- `telegram_team_summary`
- `pdf_team_report`
- `full_admin_summary`
- `sitnikov_summary`

Allowed `status` values:
- `pending`
- `generated`
- `sent`
- `failed`

Rules:
- PDF is stored locally for 6 months after challenge end.
- PDF must not be publicly accessible.
- PDF can be regenerated from Google Sheets if source data remains.

## Errors

Optional sheet for admin-visible critical errors.

Columns:
- `error_id`
- `created_at`
- `error_type`
- `severity`
- `message`
- `context`
- `resolved`
- `resolved_at`

Allowed `severity` values:
- `critical`
- `high`
- `medium`
- `low`

Notes:
- Do not store secrets in error messages.
- Avoid full raw transcriptions unless explicitly needed.

## Relationships

- `Participants.flow_id` -> `ChallengeFlows.flow_id`
- `Participants.team_id` -> `Teams.team_id`
- `Participants.captain_id` -> `Participants.participant_id`
- `Participants.tracker_id` -> `Trackers.tracker_id`
- `Teams.flow_id` -> `ChallengeFlows.flow_id`
- `Teams.captain_id` -> `Participants.participant_id`
- `Teams.tracker_id` -> `Trackers.tracker_id`
- `Goals.participant_id` -> `Participants.participant_id`
- `PlannedSteps.participant_id` -> `Participants.participant_id`
- `PlannedSteps.goal_id` -> `Goals.goal_id`
- `WeeklyReports.participant_id` -> `Participants.participant_id`
- `WeeklyReports.team_id` -> `Teams.team_id`
- `WeeklyReports.goal_id` -> `Goals.goal_id`
- `WeeklyReportSteps.weekly_report_id` -> `WeeklyReports.weekly_report_id`
- `WeeklyReportSteps.step_id` -> `PlannedSteps.step_id`
- `Insights.participant_id` -> `Participants.participant_id`
- `Insights.goal_id` -> `Goals.goal_id`
- `ReportRuns.team_id` -> `Teams.team_id`

## Validation Rules

Before bot uses the sheet data, validate:
- required IDs are present
- `participant_id` is unique
- `telegram_id` is unique where present
- role values are allowed
- status values are allowed
- each active participant has `team_id`, `captain_id`, `tracker_id`, active goal, and planned steps
- each team has captain and tracker
- report status code, symbol, and score match
- no captain is assigned outside own team unless explicitly configured
- trackers must not change sheet structure, column names, technical IDs, or service fields
- `WeeklyReportSteps` exists for every `green` and `blue` weekly report
- no closed planned step is closed again by a later report

## Access Rules

- Admin directly edits Google Sheets and owns structure/data correctness.
- Trackers may have direct access, but must not change structure, column names, technical IDs, or service fields.
- Captains and participants do not get direct Google Sheets access.
- All participant and captain writes go through Telegram bot.

## Product Decisions

Resolved product decisions are recorded in `docs/02_open_questions.md`.
