---
status: planned
depends_on: []
wave: 1
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 3: Google Sheets adapter and schema validation

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Implement the concrete Google Sheets adapter for the current `SheetsGateway` contract and add fail-fast schema validation for required tabs and columns. The adapter must support the smoke flows in the approved user-spec without changing business rules in services.

The Google Sheet remains the business store. SQLite must not receive any new business-primary tables as part of this task.

## What to do

- Add a Google Sheets API v4 implementation of all current `SheetsGateway` methods.
- Add a required schema registry for the tabs and columns used by current MVP services.
- Add a validator that fails on missing required tabs/columns and allows extra columns.
- Preserve the existing `FakeSheetsGateway` for tests and local flows.
- Add unit tests with fake Sheets API/service objects; do not require real credentials.
- Add dependency metadata needed for Google API access.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_participant_sheets_gateway.py::test_live_gateway_finds_participant_by_telegram_id` - row mapping works.
- `tests/test_weekly_report_sheets_gateway.py::test_live_gateway_appends_weekly_report_and_steps` - append behavior matches contract.
- `tests/test_insight_sheets_gateway.py::test_live_gateway_appends_and_lists_insights` - insight reads/writes work.
- `tests/test_reports_sheets_gateway.py::test_live_gateway_lists_report_facts` - report aggregation reads are supported.
- A schema validation test for missing tab/column failure and extra column success.

## Acceptance Criteria

- [ ] Live adapter implements every method in `SheetsGateway`.
- [ ] Required schema validation covers `Participants`, `Teams`, `Trackers`, `Goals`, `PlannedSteps`, `WeeklyReports`, `WeeklyReportSteps`, and `Insights`.
- [ ] Missing required tabs or columns fail before user flows.
- [ ] Extra columns do not fail validation.
- [ ] Tests use fake service objects and no real Google credentials.
- [ ] Adapter errors are sanitized and do not expose credential file contents.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [docs/04_google_sheets_schema.md](/root/telegram_goals_bot/docs/04_google_sheets_schema.md)
- [app/sheets/gateway.py](/root/telegram_goals_bot/app/sheets/gateway.py)
- [app/services/participant_flows.py](/root/telegram_goals_bot/app/services/participant_flows.py)
- [app/services/weekly_reports.py](/root/telegram_goals_bot/app/services/weekly_reports.py)
- [app/services/insights.py](/root/telegram_goals_bot/app/services/insights.py)
- [app/services/captains.py](/root/telegram_goals_bot/app/services/captains.py)
- [tests/test_participant_sheets_gateway.py](/root/telegram_goals_bot/tests/test_participant_sheets_gateway.py)
- [tests/test_weekly_report_sheets_gateway.py](/root/telegram_goals_bot/tests/test_weekly_report_sheets_gateway.py)
- [tests/test_insight_sheets_gateway.py](/root/telegram_goals_bot/tests/test_insight_sheets_gateway.py)
- [tests/test_reports_sheets_gateway.py](/root/telegram_goals_bot/tests/test_reports_sheets_gateway.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py tests/test_insight_sheets_gateway.py tests/test_reports_sheets_gateway.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py tests/test_insight_sheets_gateway.py tests/test_reports_sheets_gateway.py -v` -> all pass

## Details

**Files:**
- `app/sheets/gateway.py` - add live adapter, schema registry, schema validator, sanitized exceptions.
- `tests/test_*sheets_gateway.py` - add live-adapter unit tests alongside fake gateway tests.
- `pyproject.toml` - add Google API dependencies if required.

**Dependencies:** None. Runtime composition will pass credentials/settings after Task 1; this adapter task should remain testable with explicit fake service objects.

**Edge cases:**
- Boolean values in Sheets may appear as strings.
- Empty cells should map to empty strings or safe defaults consistently.
- Manual extra columns must not break adapter reads.
- Missing columns must fail with tab/column names, not raw credential details.

**Implementation hints:**
- Keep tab names and column names centralized.
- Keep row mapping deterministic: header row defines keys, following rows define values.
- Use append/update operations narrowly; do not rewrite whole sheets unless necessary.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-3/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-3/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-3/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
