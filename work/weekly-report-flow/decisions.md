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
