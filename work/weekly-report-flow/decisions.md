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
