---
created: 2026-07-08
status: approved
branch: dev
size: L
---

# Tech Spec: reports-flow

## Solution

Implement local, adapter-independent report generation and delivery for the MVP reports phase.

The feature adds:

- Report domain models for team summaries, participant report sections, full summaries, group comparison, recipients, and delivery results.
- Report-oriented Sheets gateway reads over final business facts.
- SQLite technical state for report generation and delivery idempotency.
- Team report aggregation from Google Sheets rows.
- Russian short Telegram team report formatting.
- A dependency-free MVP PDF renderer that writes simple local PDF files under the existing `reports/pdf/` path policy.
- Bot client and notification routing support for document delivery through the notification bot.
- Role-safe report delivery orchestration for captains, trackers, admin, and Alexander Sitnikov.
- Local pytest coverage with fake Sheets, fake bot clients, fake PDF generation, and temporary SQLite.

No production deploy, live Telegram document sending, live Google API adapter, public links, Docker, Redis, Celery, PostgreSQL, or web UI are included in this feature.

## Architecture

### What we're building/modifying

- **`app/reports/models.py`** — report DTOs for team summaries, participant sections, recipient plans, and delivery results.
- **`app/reports/aggregation.py`** — build report-ready team/global data from Sheets final facts.
- **`app/reports/formatting.py`** — Russian Telegram report and group/full summary text formatting.
- **`app/reports/pdf.py`** — dependency-free MVP PDF renderer using local file paths from `StoragePathPolicy`.
- **`app/reports/delivery.py`** — role-safe delivery planning and send orchestration through `NotificationRouter`.
- **`app/reports/service.py`** — high-level report generation/send service for a week.
- **`app/reports/generator.py`** — extend existing report boundary types where useful rather than replacing them.
- **`app/bot/clients.py`** — add document delivery boundary and fake client support.
- **`app/services/notifications.py`** — route report messages/documents through notification bot.
- **`app/sheets/gateway.py`** — add report-oriented read methods needed for team/global report aggregation.
- **`app/storage/reports.py`** — SQLite repository for report job runs and delivery idempotency.
- **`app/storage/sqlite.py`** — add technical report tables and schema tests.
- **`tests/test_reports_*.py`** — local fake-boundary tests for aggregation, formatting, PDF rendering, routing, idempotency, and failures.

### How it works

Report generation flow:

1. Caller invokes `ReportService.generate_and_send_week(week_number, now=...)`.
2. Service starts a technical report job run in SQLite using an idempotency key for `reports:week_{NN}`.
3. Service reads final business facts through `SheetsGateway`:
   - participants,
   - teams,
   - trackers,
   - goals,
   - planned steps,
   - weekly reports,
   - weekly report step relations,
   - insights.
4. Aggregation builds one `TeamReportData` per team and one global `AllTeamsReportData`.
5. Formatter creates a short Telegram summary for each team.
6. PDF renderer writes one local PDF file per team under `reports/pdf/{year}/week_{NN}/{team_slug}/`.
7. Formatter creates full admin/Sitnikov summary and group comparison text.
8. Delivery planner resolves authorized recipients:
   - captain: own team summary + own team PDF,
   - tracker: assigned teams only,
   - admin: all team summaries, all PDFs, full summary, group comparison,
   - Sitnikov: all team summaries, all PDFs, full summary, group comparison.
9. Delivery sends text and documents through `NotificationCategory.REPORT_DELIVERY`, which uses notification bot only.
10. For each recipient/report item, the service checks SQLite delivery state before sending. Already successful sends are skipped.
11. Missing chat id, send failure, or PDF generation failure records an error and sends a sanitized technical admin error through error bot. Processing continues for unrelated teams/recipients where possible.
12. Service finishes the report job run with completed or failed status and returns counts.

### Shared resources

| Resource | Owner (creates) | Consumers | Instance count |
|----------|----------------|-----------|----------------|
| SQLite connection per operation | Report repository | Report service | Per repository operation |
| Existing bot clients | Application composition / tests | NotificationRouter, ReportDeliveryService | 3 existing bot clients |
| Existing Sheets gateway | Application composition / tests | Report aggregation/service | 1 gateway per service graph |
| Local PDF files | PDF renderer | Report delivery, retention policy | 1 file per team/week |

## Decisions

### Decision 1: Reports read only final Google Sheets facts
**Decision:** Report aggregation reads Google Sheets final business rows and must not read SQLite drafts as report content.
**Rationale:** Supports US-09: reports use final business facts and do not include unfinished SQLite drafts.
**Alternatives considered:** Include active drafts to show late or incomplete work. Rejected because drafts are technical state and can leak unfinished text.

### Decision 2: Use SQLite only for technical report job/delivery state
**Decision:** Add technical SQLite tables named `report_job_runs` and `report_delivery_log`; do not create a SQLite `report_runs` table because current schema treats `report_runs` as a business-primary table name.
**Rationale:** Supports US-23 and avoids violating the storage boundary that final report facts belong in Google Sheets.
**Alternatives considered:** Use a `report_runs` SQLite table. Rejected because it conflicts with existing `BUSINESS_PRIMARY_TABLES` guard.

### Decision 3: Generate dependency-free MVP PDFs
**Decision:** Implement a simple local PDF renderer with the Python standard library instead of adding a runtime PDF package in this feature.
**Rationale:** Supports US-03, US-04, and US-24 while keeping the MVP dependency surface small and local tests install-free.
**Alternatives considered:** Add ReportLab or WeasyPrint. Rejected for this feature because the project currently has no runtime dependencies and the MVP PDF style is intentionally simple.

### Decision 4: Extend bot boundary for documents
**Decision:** Add `send_document` to the bot client boundary and fake bot client, then route documents through notification bot for report delivery.
**Rationale:** Supports US-03, US-11 through US-18, and the project three-bot architecture.
**Alternatives considered:** Send PDF paths as text or public links. Rejected because PDFs must be files, local, and non-public.

### Decision 5: Recipient-level idempotency
**Decision:** Store delivery state per week, report type, team/global scope, recipient type, and recipient id/chat id so reruns skip already successful sends.
**Rationale:** Supports US-22 and protects recipients from duplicate report spam after retries or scheduler reruns.
**Alternatives considered:** Make the whole report job all-or-nothing. Rejected because one failed recipient must not block others.

### Decision 6: Group comparison is a separate admin/Sitnikov-only report type
**Decision:** Model group comparison separately from team reports and exclude captain/tracker recipient types at the delivery-planning layer.
**Rationale:** Supports US-15, US-18, and the privacy rule that captains and trackers do not receive group comparison.
**Alternatives considered:** Include group comparison inside tracker or captain PDFs. Rejected due to explicit access restrictions.

### Decision 7: Audio files are never opened during report generation
**Decision:** Reports render `transcription_text` and audio path metadata only; they do not open or attach original audio files.
**Rationale:** Supports US-10 and retention rules: audio can be deleted while transcription remains available.
**Alternatives considered:** Attach original audio files when present. Rejected as out of MVP for report delivery and risky after retention cleanup.

## Data Models

### SheetsGateway additions

Add report-oriented read methods with fake implementation:

- `list_goals() -> list[SheetRow]`
- `list_planned_steps_all() -> list[SheetRow]`
- `list_weekly_reports_for_week(week_number: int) -> list[SheetRow]`
- `list_weekly_report_steps_all() -> list[SheetRow]`
- `list_insights_for_week(week_number: int) -> list[SheetRow]`

Existing methods remain available for participant/captain flows.

### Report DTOs

Expected report models:

- `ParticipantReportSection`
  - participant id, team id, full name, username, status, dropped/risk state,
  - progress bar, progress percent,
  - goal fields,
  - planned/completed/partial steps,
  - report text, transcription text, insights.
- `TeamReportData`
  - week number, team row, captain row,
  - active count, dropped count,
  - status distribution,
  - weekly victory percent,
  - participant sections.
- `AllTeamsReportData`
  - week number,
  - team summaries,
  - group comparison fields,
  - global counts.
- `ReportRecipient`
  - recipient type,
  - recipient id,
  - chat id,
  - team scope.
- `ReportDeliveryItem`
  - report type,
  - team id or global scope,
  - text or file path,
  - recipient.
- `ReportRunResult`
  - generated count,
  - sent count,
  - skipped count,
  - failed count.

### SQLite technical tables

Add tables through `app/storage/sqlite.py`:

- `report_job_runs`
  - `report_job_run_id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `week_number INTEGER NOT NULL`
  - `job_type TEXT NOT NULL CHECK (job_type IN ('report_generate_send'))`
  - `idempotency_key TEXT NOT NULL UNIQUE`
  - `started_at TEXT NOT NULL`
  - `finished_at TEXT`
  - `status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'skipped'))`
  - `error_message TEXT`
- `report_delivery_log`
  - `report_delivery_id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `week_number INTEGER NOT NULL`
  - `report_type TEXT NOT NULL`
  - `scope_id TEXT NOT NULL`
  - `recipient_type TEXT NOT NULL`
  - `recipient_id TEXT NOT NULL`
  - `chat_id TEXT NOT NULL`
  - `status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped'))`
  - `sent_at TEXT NOT NULL`
  - `telegram_message_id INTEGER`
  - `file_path TEXT`
  - `error_message TEXT`
  - `attempt_count INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count > 0)`
  - unique `(week_number, report_type, scope_id, recipient_type, recipient_id)`

Do not add these table names to `BUSINESS_PRIMARY_TABLES`; they are technical state.

## Dependencies

### New packages

None.

### Using existing (from project)

- `app.scheduler.calendar` — current week and challenge year semantics where needed.
- `app.storage.paths` — PDF local path policy and retention constants.
- `app.sheets.gateway` — final business facts.
- `app.services.notifications` — three-bot routing.
- `app.bot.clients` — fake/local bot boundary, extended for document delivery.
- `app.reports.generator` — existing report boundary, extended where useful.
- `app.storage.sqlite` — technical state schema.

## Testing Strategy

**Feature size:** L

### Unit tests

- Team progress percent and 6-cell progress bar calculation.
- Weekly victory percent excludes dropped participants.
- Status distribution for green/blue/red/gray.
- Dropped and risk participant section classification.
- Insight exclusion from progress.
- Short Telegram report formatter.
- Full summary and group comparison formatter.
- Recipient resolution for captain/tracker/admin/Sitnikov.
- Delivery idempotency key behavior.
- PDF renderer writes a local PDF-like file under safe path.

### Integration tests

- Aggregation from fake Sheets builds correct team report data.
- PDF team report generation uses local path policy and includes required participant content.
- Reports ignore unfinished SQLite drafts.
- Deleted audio path does not break report generation.
- Captain receives only own team summary/PDF.
- Tracker receives only assigned gender/team reports.
- Admin and Sitnikov receive all reports and group comparison.
- Captains and trackers never receive group comparison.
- Missing recipient chat id notifies admin and does not block other recipients.
- Send failure for one recipient notifies admin and does not block others.
- PDF generation failure for one team notifies admin and continues other teams.
- Rerun skips already successful delivery items.
- Existing participant, captain, scheduler, and weekly report tests remain green.

### E2E tests

None for this local feature. Live Telegram document sending and live Google Sheets verification are deferred to deployment/post-deploy verification.

## Agent Verification Plan

**Source:** user-spec "How to Verify" section.

### Verification approach

Run local pytest suites only. Use fake Sheets, fake bot clients, fake/standard-library PDF renderer, local temp paths, and temporary SQLite. No live Telegram, live Google Sheets, external API, browser, deploy, or production server verification is required.

### Tools required

- bash
- pytest
- Python import/file assertions

## Risks

| Risk | Mitigation |
|------|-----------|
| Cross-team report data leak | Centralize delivery planning and test captain/tracker/admin/Sitnikov scopes. |
| Group comparison leak | Model group comparison as admin/Sitnikov-only and add negative routing tests. |
| Draft data appears in reports | Aggregation reads only Sheets gateway final rows. |
| Duplicate report sends after rerun | SQLite recipient-level delivery idempotency. |
| PDF generation failure hides reports | Per-team generation isolation and admin technical errors. |
| Generated files committed | Use temp dirs in tests and artifact scans during QA. |
| New PDF dependency complicates MVP | Use dependency-free MVP renderer in this feature. |

## User-Spec Deviations

None.

## Acceptance Criteria

Technical acceptance criteria complement the user-facing criteria from `user-spec.md`:

- [ ] Report aggregation reads final Google Sheets rows through `SheetsGateway`.
- [ ] SQLite report state uses technical table names and does not create a business-primary `report_runs` table.
- [ ] PDF renderer writes local non-public files under `StoragePathPolicy.pdf_path`.
- [ ] Bot document delivery is represented in the bot boundary and fake client.
- [ ] `NotificationCategory.REPORT_DELIVERY` uses notification bot only.
- [ ] Recipient planner enforces captain, tracker, admin, and Sitnikov scopes.
- [ ] Group comparison cannot be delivered to captains or trackers.
- [ ] Report delivery is idempotent per recipient/report item.
- [ ] Admin errors are sanitized and do not include secrets or raw personal report text.
- [ ] Existing foundation, participant, weekly report, captain, insight, voice, and scheduler tests remain green.
- [ ] No runtime dependency, deploy config, live adapter, generated PDF, SQLite DB, credential, or secret is committed.

## Implementation Tasks

### Wave 1 (foundations)

#### Task 1: Report Models and Text Formatters
- **Description:** Add report DTOs and Russian text formatters for team summaries, full summaries, group comparison, and participant lines. This gives later aggregation and delivery code stable report contracts without embedding presentation strings in orchestration.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/reports/models.py`, `app/reports/formatting.py`, `tests/test_reports_messages.py`
- **Files to read:** `work/reports-flow/user-spec.md`, `docs/07_reports.md`, `app/bot/messages.py`, `app/services/participant_models.py`

#### Task 2: Report Sheets Gateway Reads
- **Description:** Extend `SheetsGateway` and `FakeSheetsGateway` with report-oriented read paths for goals, planned steps, weekly reports, weekly report step relations, and insights. This keeps report aggregation behind the existing Sheets boundary and avoids direct fake internals.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/sheets/gateway.py`, `tests/test_reports_sheets_gateway.py`
- **Files to read:** `docs/04_google_sheets_schema.md`, `app/sheets/gateway.py`, `tests/test_scheduler_sheets_gateway.py`

#### Task 3: Report SQLite Repository
- **Description:** Add technical SQLite state for report job runs and delivery idempotency without creating business-primary tables. This allows reruns to skip successful recipient/report sends while preserving Google Sheets as the final business data source.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/storage/reports.py`, `app/storage/sqlite.py`, `tests/test_reports_repository.py`, `tests/test_sqlite_schema.py`
- **Files to read:** `docs/05_sqlite_state_schema.md`, `app/storage/scheduler.py`, `tests/test_scheduler_repository.py`, `tests/test_sqlite_schema.py`

#### Task 4: Bot Document Delivery Boundary
- **Description:** Extend bot and notification boundaries so report delivery can send both text and PDF documents through notification bot fakes. This is needed for local verification of PDF delivery without live Telegram.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/bot/clients.py`, `app/services/notifications.py`, `tests/test_reports_delivery_boundary.py`
- **Files to read:** `app/bot/clients.py`, `app/services/notifications.py`, `tests/test_voice_processing_service.py`

### Wave 2 (report generation)

#### Task 5: Team Report Aggregation
- **Description:** Build team report data from Sheets final facts, including active/dropped counts, status distribution, progress bars, weekly victory percentage, goals, planned steps, weekly report text, transcriptions, and insights. The result is a reusable data layer for Telegram and PDF renderers.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/reports/aggregation.py`, `tests/test_reports_generation.py`
- **Files to read:** `app/sheets/gateway.py`, `app/services/participant_models.py`, `app/services/weekly_report_models.py`, `docs/07_reports.md`

#### Task 6: Local PDF Renderer
- **Description:** Implement the dependency-free MVP PDF renderer for team reports using the report data model and existing local path policy. The renderer should produce simple readable local files and avoid opening original audio attachments.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_reports_pdf.py -q` -> pass
- **Files to modify:** `app/reports/pdf.py`, `app/reports/generator.py`, `tests/test_reports_pdf.py`
- **Files to read:** `app/storage/paths.py`, `app/reports/generator.py`, `docs/07_reports.md`

### Wave 3 (delivery and orchestration)

#### Task 7: Recipient Planning
- **Description:** Add recipient planning for captains, trackers, admin, and Sitnikov using team/tracker scope rules. This isolates role-safe routing before any messages or documents are sent.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/reports/delivery.py`, `tests/test_reports_delivery.py`
- **Files to read:** `work/reports-flow/user-spec.md`, `docs/07_reports.md`, `app/sheets/gateway.py`, `app/services/notifications.py`

#### Task 8: Report Delivery Service
- **Description:** Send team summaries, PDFs, full summaries, and group comparison through notification bot with recipient-level idempotency and isolated error handling. The service must skip successful prior sends and notify admin for missing chat ids or send failures.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/reports/delivery.py`, `app/reports/service.py`, `tests/test_reports_delivery.py`
- **Files to read:** `app/storage/reports.py`, `app/services/notifications.py`, `app/bot/clients.py`

#### Task 9: Report Orchestration Service
- **Description:** Add the high-level weekly report generation/send entry point that coordinates aggregation, Telegram summaries, PDF rendering, full summary, group comparison, and delivery. This becomes the local scheduler/manual-call boundary for the reports phase.
- **Skill:** code-writing
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Files to modify:** `app/reports/service.py`, `tests/test_reports_service.py`
- **Files to read:** `app/reports/aggregation.py`, `app/reports/pdf.py`, `app/reports/delivery.py`, `app/storage/reports.py`

### Wave 4 (regressions)

#### Task 10: Reports Boundary and Regression Coverage
- **Description:** Broaden report tests around privacy, idempotency, generation failure, deleted audio paths, generated artifact safety, and existing flow regressions. This protects the high-risk report routing and storage boundaries before audits.
- **Skill:** test-master
- **Reviewers:** code-reviewer, security-auditor, test-reviewer
- **Verify-smoke:** `.venv/bin/python -m pytest tests/test_reports_generation.py tests/test_reports_delivery.py tests/test_reports_service.py tests/test_reports_boundaries.py -q` -> pass
- **Files to modify:** `tests/test_reports_boundaries.py`, existing report tests if needed
- **Files to read:** `work/reports-flow/user-spec.md`, `work/reports-flow/tech-spec.md`, `docs/07_reports.md`

### Audit Wave

#### Task 11: Code Audit
- **Description:** Full-feature code quality audit. Read all report source and test files created or modified in this feature and review architecture, maintainability, idempotency, and cross-component consistency.
- **Skill:** code-reviewing
- **Reviewers:** none
- **Files to modify:** `work/reports-flow/logs/working/task-11/code-audit.json`
- **Files to read:** `work/reports-flow/user-spec.md`, `work/reports-flow/tech-spec.md`, `work/reports-flow/decisions.md`, `app/reports/`, `app/storage/reports.py`, report tests

#### Task 12: Security Audit
- **Description:** Full-feature security audit focused on role-safe report routing, group comparison privacy, personal data exposure, generated file safety, sanitized admin errors, and secret leakage. Write a structured JSON audit report.
- **Skill:** security-auditor
- **Reviewers:** none
- **Files to modify:** `work/reports-flow/logs/working/task-12/security-audit.json`
- **Files to read:** `work/reports-flow/user-spec.md`, `work/reports-flow/tech-spec.md`, `docs/07_reports.md`, report source and tests

#### Task 13: Test Audit
- **Description:** Full-feature test quality audit for report aggregation, PDF rendering, delivery routing, idempotency, and privacy boundaries. Verify tests are behavior-oriented and catch the high-risk routing/data-leak scenarios.
- **Skill:** test-master
- **Reviewers:** none
- **Files to modify:** `work/reports-flow/logs/working/task-13/test-audit.json`
- **Files to read:** `work/reports-flow/user-spec.md`, `work/reports-flow/tech-spec.md`, report tests

### Final Wave

#### Task 14: Pre-deploy QA
- **Description:** Run local acceptance testing for reports-flow and verify all user-spec and tech-spec acceptance criteria. No production deploy, live Telegram, or live Google Sheets verification is included in this feature.
- **Skill:** pre-deploy-qa
- **Reviewers:** none
- **Verify-smoke:** `.venv/bin/python -m pytest` -> pass
- **Files to modify:** `work/reports-flow/logs/working/task-14/pre-deploy-qa.json`, `work/reports-flow/decisions.md`
- **Files to read:** `work/reports-flow/user-spec.md`, `work/reports-flow/tech-spec.md`, `tests/`
