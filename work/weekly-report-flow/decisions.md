# Decisions Log: weekly-report-flow

## Task 1: Weekly report message and status contracts

Summary: Added adapter-independent weekly report status contracts and Russian message helpers for status prompts, validation copy, voice rejection, and success confirmations.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_messages.py -q` -> 5 passed.
- `.venv/bin/python -m pytest tests/test_participant_messages.py -q` -> 8 passed.
- `.venv/bin/python -m pytest -q` -> 78 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-1/code-reviewer-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-1/test-reviewer-1.json`

Deviations: None.

## Task 8: Code Audit

Summary: Completed weekly-report-flow code audit. No blocking code-quality findings were found.

Verification:
- `.venv/bin/python -m pytest -q` -> 121 passed.

Reviews:
- Code audit: `work/weekly-report-flow/logs/working/task-8/code-audit.json`

Deviations: None.

## Task 9: Security Audit

Summary: Completed weekly-report-flow security audit for participant isolation, consent gating, deadline/duplicate guards, storage boundaries, notification content, and out-of-scope runtime boundaries. No blocking security findings were found.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_boundaries.py -q` -> 6 passed.
- `.venv/bin/python -m pytest -q` -> 121 passed.

Reviews:
- Security audit: `work/weekly-report-flow/logs/working/task-9/security-audit.json`

Deviations: None.

## Task 10: Test Audit

Summary: Completed weekly-report-flow test audit. Coverage matches the approved user-spec and tech-spec scope with local fake-boundary and temp-SQLite tests.

Verification:
- `.venv/bin/python -m pytest -q` -> 121 passed.

Reviews:
- Test audit: `work/weekly-report-flow/logs/working/task-10/test-audit.json`

Deviations: None.

## Task 7: Weekly report boundary regression tests

Summary: Added boundary regression coverage for cross-participant step rejection, late and duplicate finalization, invalid draft recovery, missing data notifications, out-of-scope imports, and SQLite business-boundary preservation.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_boundaries.py -q` -> 6 passed.
- `.venv/bin/python -m pytest -q` -> 121 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-7/code-reviewer-1.json`
- Security review: `work/weekly-report-flow/logs/working/task-7/security-auditor-1.json`

Deviations: None.

## Task 6: Text draft collection and final save

Summary: Completed text draft collection and final weekly report save flow, including green/blue/red final facts, WeeklyReportSteps relations, green planned-step closure, empty-text guard, voice rejection, duplicate/late guards, and SQLite draft cleanup.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_start_flow.py tests/test_weekly_report_step_selection.py tests/test_weekly_report_finalize.py -q` -> 21 passed.
- `.venv/bin/python -m pytest -q` -> 115 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-6/code-reviewer-1.json`
- Security review: `work/weekly-report-flow/logs/working/task-6/security-auditor-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-6/test-reviewer-1.json`

Deviations: None.

## Task 5: Start, status selection, and step selection service flow

Summary: Added service-level weekly report start, status selection, and step selection flow with Telegram ID identity lookup, consent/deadline/duplicate gates, missing-data notifications, and SQLite draft state updates.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_start_flow.py tests/test_weekly_report_step_selection.py -q` -> 12 passed.
- `.venv/bin/python -m pytest -q` -> 106 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-5/code-reviewer-1.json`
- Security review: `work/weekly-report-flow/logs/working/task-5/security-auditor-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-5/test-reviewer-1.json`

Deviations: None.

## Task 4: Weekly report calendar helper

Summary: Added deterministic weekly report calendar helpers for current challenge week, Sunday 23:59 Yekaterinburg deadline, and open/closed deadline checks.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_calendar.py tests/test_scheduler_foundation.py -q` -> 11 passed.
- `.venv/bin/python -m pytest -q` -> 94 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-4/code-reviewer-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-4/test-reviewer-1.json`

Deviations: None.

## Task 3: Weekly report draft repository

Summary: Added a SQLite repository for weekly report technical draft state, including draft creation, selected status/steps, ordered text messages, active draft loading, stale-state recovery, and cleanup.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py tests/test_dialog_state_repository.py tests/test_sqlite_schema.py -q` -> 17 passed.
- `.venv/bin/python -m pytest -q` -> 89 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-3/code-reviewer-1.json`
- Security review: `work/weekly-report-flow/logs/working/task-3/security-auditor-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-3/test-reviewer-1.json`

Deviations: None.

## Task 2: Weekly report Sheets boundary

Summary: Extended the Sheets gateway protocol and fake implementation with participant/week duplicate lookup, WeeklyReportSteps relation storage, and participant/goal-scoped planned-step closure.

Verification:
- `.venv/bin/python -m pytest tests/test_weekly_report_sheets_gateway.py -q` -> 5 passed.
- `.venv/bin/python -m pytest tests/test_participant_sheets_gateway.py tests/test_boundaries.py -q` -> 13 passed.
- `.venv/bin/python -m pytest -q` -> 83 passed.

Reviews:
- Code review: `work/weekly-report-flow/logs/working/task-2/code-reviewer-1.json`
- Security review: `work/weekly-report-flow/logs/working/task-2/security-auditor-1.json`
- Test review: `work/weekly-report-flow/logs/working/task-2/test-reviewer-1.json`

Deviations: None.
