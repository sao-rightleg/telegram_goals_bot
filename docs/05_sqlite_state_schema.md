# SQLite State Schema

## Purpose

SQLite stores technical bot state on the VPS.

It is not the MVP business database. Final business facts must be written to Google Sheets.

## Storage Boundary

SQLite may store:
- active dialog state
- current flow and step
- draft answers
- temporary message buffers
- selected participant for captain manual report
- selected week and selected status
- selected planned step IDs for green and blue reports
- voice processing draft state
- scheduler jobs and job runs
- retry state
- technical error events

SQLite must not be the only source for:
- participant profile
- consent
- goals
- planned steps
- final weekly reports
- final insights
- dropped status
- final report facts

## Design Principles

- Bot should survive restart without losing active drafts when practical.
- Drafts are saved before final Google Sheets write.
- Drafts are cleared only after successful final save.
- Scheduler actions should be idempotent.
- Deadline rules must be checked against Yekaterinburg time.
- Stale or invalid state should return user safely to menu and notify admin if needed.
- Sensitive data should be minimized.
- Schema implementation must add concrete primary keys, unique constraints, indexes, and `CHECK` constraints where SQLite can enforce allowed technical values.
- IDs that reference Google Sheets business objects are stored as external IDs only. SQLite must not define business-owner tables for participants, teams, goals, planned steps, reports, or insights.
- Multi-value technical selections such as selected planned steps are stored as JSON text in SQLite and validated in application code.

## Physical Schema Decisions

Use SQLite standard types and constraints:

- `INTEGER PRIMARY KEY AUTOINCREMENT` for local technical event/message IDs.
- `TEXT PRIMARY KEY` for externally generated technical IDs such as `draft_id` and scheduler `job_id`.
- ISO-8601 timezone-aware text timestamps for `created_at`, `updated_at`, `expires_at`, `scheduled_for`, `started_at`, `finished_at`, and `sent_at`.
- `CHECK` constraints for known enum-like values where practical.
- `UNIQUE` constraints for idempotency:
  - one active `dialog_states` row per `telegram_id`;
  - one draft message order per `draft_id`;
  - one scheduler job per `job_type`, `week_number`, and `scheduled_for`;
  - one job run per `idempotency_key`;
  - one reminder per `participant_id`, `week_number`, and `reminder_type`.
- Indexes for lookup paths used by bot and scheduler:
  - dialog by `telegram_id`;
  - drafts by `draft_id`, `participant_id`, `telegram_id`, and `expires_at`;
  - scheduler jobs by `status` and `scheduled_for`;
  - reminders by `participant_id`, `week_number`, and `status`;
  - errors by `created_at`, `severity`, and `admin_notified`.

## Tables

## draft_sessions

Stores the shared technical draft identity used by report, insight, message, and attachment draft tables.

Columns:
- `draft_id`
- `draft_type`
- `participant_id`
- `telegram_id`
- `flow_source`
- `status`
- `created_at`
- `updated_at`
- `expires_at`

Allowed `draft_type` values:
- `weekly_report`
- `insight`
- `captain_manual_report`

Allowed `status` values:
- `active`
- `saving`
- `saved`
- `failed`
- `expired`

Rules:
- `draft_id` is the technical join key for draft-related tables.
- Draft session state is technical and temporary.
- Final report or insight facts still belong to Google Sheets.

## dialog_states

Stores current active flow per Telegram user.

Columns:
- `telegram_id`
- `participant_id`
- `role`
- `flow`
- `step`
- `week_number`
- `selected_status`
- `selected_participant_id`
- `selected_step_ids`
- `draft_id`
- `started_at`
- `updated_at`
- `expires_at`

Suggested `flow` values:
- `consent`
- `weekly_report`
- `insight`
- `captain_manual_report`
- `view_goal`
- `view_steps`
- `view_progress`
- `view_team`
- `idle`

Notes:
- `selected_participant_id` is used for captain manual report.
- `selected_step_ids` is required before saving `green` or `blue` reports.
- `selected_step_ids` may contain multiple step IDs because one weekly report can close or partially progress several steps.

## draft_messages

Stores ordered draft text and transcription fragments.

Columns:
- `draft_message_id`
- `draft_id`
- `participant_id`
- `telegram_id`
- `message_order`
- `message_type`
- `text`
- `telegram_message_id`
- `created_at`

Allowed `message_type` values:
- `text`
- `voice_transcription`
- `system_note`

Rules:
- Preserve message order.
- Final report or insight text is assembled only after `✅ Готово`.

## draft_attachments

Stores temporary local file references for voice messages.

Columns:
- `draft_attachment_id`
- `draft_id`
- `participant_id`
- `telegram_file_id`
- `local_file_path`
- `duration_seconds`
- `transcription_status`
- `transcription_text`
- `error_message`
- `created_at`
- `updated_at`

Allowed `transcription_status` values:
- `pending`
- `success`
- `failed`

Rules:
- Voice over 10 minutes must not be accepted.
- Local file path must not be public.
- Failed transcription should not silently drop the draft.

## draft_reports

Stores report-level draft metadata before final save to Google Sheets.

Columns:
- `draft_id`
- `participant_id`
- `team_id`
- `goal_id`
- `week_number`
- `flow_source`
- `status_code`
- `status_symbol`
- `submitted_by_id`
- `submitted_by_role`
- `selected_step_ids`
- `created_at`
- `updated_at`

Allowed `flow_source` values:
- `participant_bot`
- `captain_manual`

Notes:
- `selected_step_ids` is required for `green` and `blue`.
- `green` means selected steps will be saved as `closed` relations in Google Sheets.
- `blue` means selected steps will be saved as `partial` relations in Google Sheets.
- `selected_step_ids` may be empty only for `red` or non-status-changing late text.
- Final weekly report must be stored in Google Sheets.

## draft_insights

Stores insight-level draft metadata before final save to Google Sheets.

Columns:
- `draft_id`
- `participant_id`
- `goal_id`
- `week_number`
- `insight_scope`
- `created_by_id`
- `created_by_role`
- `created_at`
- `updated_at`

Allowed `insight_scope` values:
- `current_week`
- `previous_week`
- `goal_general`

## scheduler_jobs

Stores known scheduled job definitions and current state.

Columns:
- `job_id`
- `job_type`
- `week_number`
- `scheduled_for`
- `timezone`
- `status`
- `created_at`
- `updated_at`

Suggested `job_type` values:
- `monday_reminder`
- `wednesday_checkin`
- `sunday_1800_checkin`
- `sunday_2230_reminder`
- `sunday_2300_reminder`
- `week_close`
- `report_generate`
- `report_send`
- `audio_cleanup`
- `sqlite_backup`
- `google_sheets_export`
- `pdf_retention_check`

Allowed `status` values:
- `pending`
- `running`
- `completed`
- `failed`
- `skipped`

## job_runs

Stores actual job run attempts.

Columns:
- `job_run_id`
- `job_id`
- `job_type`
- `week_number`
- `started_at`
- `finished_at`
- `status`
- `idempotency_key`
- `error_message`

Rules:
- Use idempotency keys for weekly closing and report sending.
- Duplicate run should not create duplicate gray reports or duplicate sends.

## reminder_log

Stores reminder sends to prevent duplicates.

Columns:
- `reminder_log_id`
- `participant_id`
- `team_id`
- `week_number`
- `reminder_type`
- `sent_at`
- `telegram_message_id`
- `status`
- `error_message`

Suggested `reminder_type` values:
- `monday_start`
- `wednesday_checkin`
- `sunday_1800`
- `sunday_2230`
- `sunday_2300`

## error_events

Stores local technical error references.

Columns:
- `error_event_id`
- `created_at`
- `module`
- `error_type`
- `severity`
- `participant_id`
- `team_id`
- `message`
- `admin_notified`
- `resolved`

Notes:
- Do not store secrets.
- Avoid full personal data where IDs are enough.

## State Lifecycle

1. User starts a flow.
2. Bot writes or updates `dialog_states`.
3. Bot collects text and voice fragments into draft tables.
4. User presses `✅ Готово`.
5. Bot validates deadline, permissions, and required data.
6. Bot writes final business fact to Google Sheets.
7. Bot clears related dialogue state and drafts.
8. Bot confirms successful save.

If Google Sheets write fails, keep draft state and tell user that save did not complete.

## Deadline Protection

Before final save:
- calculate current time in `Asia/Yekaterinburg`
- verify current week is still open
- reject status-changing participant report after Sunday 23:59
- reject captain manual report after Sunday 23:59
- never create yellow late status
- allow late report text only as non-status-changing text if this flow is implemented
- require selected step IDs before saving `green` or `blue`
- reject attempts to close already closed planned steps

## Scheduler Decisions

Scheduler uses `Asia/Yekaterinburg`.

Fixed reminder schedule:
- Monday 10:00 start-of-week reminder
- Wednesday 10:00 soft check-in
- Sunday 18:00 final check-in
- Sunday 22:30 reminder for participants without weekly report
- Sunday 23:00 last reminder for participants without weekly report
- Sunday 23:59 hard deadline

Challenge calendar:
- all teams use one shared calendar
- challenge end date is `2026-07-31`
- weeks 1-2 are goal/route setup
- weeks 3-8 are six working execution weeks
- after week 8 there are four days for final summary

## Cleanup and Backup Jobs

Audio cleanup:
- delete original audio automatically one month after recording
- keep audio path and transcription in Google Sheets
- system must not try to open or send deleted audio files

SQLite backup:
- daily automatic backup
- 14-day retention

Google Sheets export:
- periodic `.xlsx` or `.csv` export
- 14-day retention
- fresh export recommended before week close and mass report sending

Backup location: `/root/telegram_goals_bot/backups/`.

## Bot Separation

SQLite state belongs to main bot user flows. Error bot and notification bot should not mutate dialogue state unless explicitly required by a future tech spec.

Technical errors are routed to error bot. Operational reminders, PDFs, and summaries are routed to notification bot.

## Open Implementation Questions

- Exact draft expiration time.
- Whether stale drafts should be auto-cleared or resumed first.
- Exact scheduler implementation and persistence strategy.
- Whether `error_events` is enough or critical errors should also be mirrored to Google Sheets.
