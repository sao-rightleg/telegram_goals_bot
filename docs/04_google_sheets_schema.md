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

## Participants

Stores all people who can interact with the bot.

Columns:
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
- `drop_reason`
- `consent_given`
- `consent_given_at`
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

## Teams

Stores teams.

Columns:
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
- Who marks a goal achieved is not decided yet.

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
- Whether one weekly report can close multiple steps is still a decision needed.

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
- `⬜`

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
- Missing report after deadline becomes `gray` / `⬜` from `system_deadline`.

## WeeklyReportSteps

Stores relation between weekly reports and planned steps if step selection is approved.

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
- This sheet is needed if one report can relate to one or more planned steps.
- Exact step-linking rules are still open.

## Insights

Stores insights separately from progress.

Columns:
- `insight_id`
- `participant_id`
- `goal_id`
- `week_number`
- `insight_scope`
- `insight_text`
- `transcription_text`
- `audio_file_path`
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

## ReportRuns

Stores report generation and sending metadata.

Columns:
- `report_run_id`
- `week_number`
- `team_id`
- `report_type`
- `pdf_file_path`
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

- `Participants.team_id` -> `Teams.team_id`
- `Participants.captain_id` -> `Participants.participant_id`
- `Participants.tracker_id` -> `Trackers.tracker_id`
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

## Open Questions / Decisions Needed

- Should consent have a separate history sheet or remain only in `Participants`?
- Should `WeeklyReportSteps` be mandatory in MVP or only added after step-linking is decided?
- If green status is selected, must a planned step be selected?
- If blue status is selected, can a planned step be linked as partial?
- Can one weekly report close multiple steps?
- Should deleted audio file paths remain in Google Sheets after retention cleanup?
- Should critical errors be duplicated in the `Errors` sheet or only sent to admin chat/logs?
