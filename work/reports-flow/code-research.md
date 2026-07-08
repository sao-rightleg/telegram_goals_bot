# Code Research: reports-flow

## Scope

Next MVP phase after scheduler deadlines: short Telegram team reports, PDF team reports, full summary for admin/Sitnikov, group comparison for admin/Sitnikov only, and role-safe report delivery.

## Existing foundation

- `docs/07_reports.md` defines MVP report types, recipients, report content, progress rules, PDF storage, and error handling.
- `app/reports/generator.py` already provides a report generation boundary:
  - `ReportType`
  - `ReportRequest`
  - `GeneratedReport`
  - `ReportGenerator` protocol
  - `FakeReportGenerator`
- `app/services/notifications.py` already has `NotificationCategory.REPORT_DELIVERY`; non-participant messages use the notification bot.
- `app/storage/paths.py` already defines local `reports/pdf/{year}/week_{NN}/{team_slug}/{file_name}` path policy and PDF retention constant.
- `app/sheets/gateway.py` can currently read participants, teams, trackers, goals, planned steps per participant, weekly reports, weekly report step rows, and insights.
- `app/storage/sqlite.py` includes `report_runs` in `BUSINESS_PRIMARY_TABLES`, but there is no technical `report_runs` table or report-run repository yet.
- `app/bot/menus.py` already exposes captain menu action `VIEW_TEAM_REPORT`, but no service behavior for viewing/sending team reports exists.

## Relevant implemented data flows

- Weekly report and captain manual report finalization write `weekly_reports` and `weekly_report_steps` facts to Google Sheets fake gateway.
- Scheduler week close creates `gray` / `⬜` weekly report facts for silent active participants.
- Insight flow writes final insights to Google Sheets and purges full saved insight draft text from SQLite.
- Voice flow writes transcription and audio file paths into final weekly report or insight rows through the owning finalization services.

## Gaps for reports-flow

1. No report aggregation service exists to build team summaries from Sheets rows.
2. No role-safe report delivery service exists.
3. No concrete PDF renderer exists; only a fake report boundary is present.
4. No report-run SQLite repository exists for idempotency, generation status, send status, retry metadata, or error state.
5. `SheetsGateway` may need report-oriented queries or helpers:
   - list goals for a team/participants,
   - list planned steps for multiple participants,
   - list insights for a team/week,
   - append/update report run metadata if final metadata belongs in Sheets.
6. Notification router currently sends text messages only; PDF delivery may need a file/document boundary or an extended bot client contract.
7. Current report generator request is team-oriented and may need models for admin summary and group comparison.

## Privacy and routing risks

- Captains must receive only own-team reports.
- Trackers receive assigned team reports only.
- Admin receives all reports and errors.
- Sitnikov receives all reports and group comparison.
- Captains and trackers must not receive group comparison.
- Dropped participants remain visible but excluded from active victory percentage.
- Reports must use final Google Sheets facts only; unfinished SQLite drafts must not appear.

## Testing implications

- Use fake Sheets, fake notification bot, fake PDF generator/renderer, temporary SQLite, and local paths.
- Add behavior tests for:
  - team report content aggregation,
  - dropped participant handling,
  - report source excluding SQLite drafts,
  - captain/tracker/admin/Sitnikov routing,
  - group comparison privacy,
  - missing recipient chat id,
  - one failed recipient does not block others,
  - idempotent report generation/send reruns,
  - PDF path safety and no committed generated PDFs.

## Recommended feature shape

Feature size: L.

Split implementation into foundations, aggregation, PDF rendering, delivery/idempotency, and QA/audits. Keep live Telegram/Google/PDF smoke out of this local feature unless a later deployment feature explicitly wires real adapters.
