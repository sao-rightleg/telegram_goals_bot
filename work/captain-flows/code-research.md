# Code Research: captain-flows

## Scope

Research for the next MVP feature after voice processing: captain menu, own-team view, captain manual weekly reports, role-safe access, and deadline protection.

## Existing foundations

- `app/bot/menus.py` already exposes captain-specific menu actions through `build_role_menu("captain")`.
- `app/services/participant_flows.py` handles `/start`, identification, consent, role-aware menu routing, goal/steps/progress views, and admin-only technical errors.
- `app/services/weekly_reports.py` owns participant weekly report start/status/step/text/finalization rules and already writes `weekly_reports` plus `weekly_report_steps`.
- `app/storage/weekly_report_drafts.py` stores draft sessions, draft reports, selected steps, ordered draft messages, and voice attachments for participant weekly reports.
- `app/storage/dialog_state.py` and SQLite schema already include `selected_participant_id`, which can support captain participant selection.
- `app/sheets/gateway.py` fake boundary supports participants, goals, planned steps, weekly reports, and weekly report step relations.
- `app/services/voice_messages.py` can append voice input into active weekly-report or insight drafts; tech spec must decide how captain manual report flow reuses or extends this.

## Gaps

- No captain-specific service module exists yet.
- No own-team participant list/read model exists.
- No captain manual report draft flow exists.
- Weekly report draft repository currently creates participant-bot drafts with submitted role `participant`; captain manual reports need selected participant and `submitted_by_role='captain'`.
- Existing weekly report service is participant-scoped and resolves the report participant from the current Telegram user, so it cannot directly submit for another own-team participant.
- Fake Sheets gateway has no dedicated team-member query helper; it can be extended or filtered in a service.
- Tests currently cover captain menu visibility only at a basic level, not full captain access boundaries.

## Suggested implementation direction

- Add a captain service that resolves the current Telegram user as role `captain`, loads own-team participants, and starts a manual report for a selected participant from that team.
- Reuse weekly report status, step selection, duplicate guard, deadline guard, and final row conventions where possible.
- Store captain manual draft state in existing SQLite tables with `draft_type='weekly_report'` or `captain_manual_report` only after tech spec confirms the cleanest repository boundary.
- Final Google Sheets row should remain a weekly report for the selected participant and include `submitted_by_id` as captain participant id and `submitted_by_role='captain'`.
- Add regressions for other-team participant denial, dropped participant denial, duplicate report denial, late status denial, green/blue step selection requirement, and no cross-team data leakage.

## Verification focus

- Local pytest with fake Sheets and temporary SQLite.
- No live Telegram, Google Sheets, or deploy required for this feature slice.
