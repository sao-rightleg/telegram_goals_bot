# Decisions Log: participant-core-flows

## Task 1: Participant domain and message contracts

Summary: Added adapter-independent participant flow contracts, role-aware menu definitions, and Russian message/view formatters for approved participant core flows.

Verification:
- `.venv/bin/python -m pytest tests/test_participant_messages.py -v` -> 8 passed.
- `.venv/bin/python -m pytest -q` -> 43 passed.

Reviews:
- Code review: `work/participant-core-flows/logs/working/task-1/code-reviewer-1.json`
- Security review: `work/participant-core-flows/logs/working/task-1/security-auditor-1.json`
- Test review: `work/participant-core-flows/logs/working/task-1/test-reviewer-1.json`

Deviations: None.

## Task 2: Participant Sheets boundary

Summary: Extended the Sheets gateway protocol and fake implementation with participant identity lookup, consent writes, active goal reads, planned-step reads, and participant-scoped weekly history.

Verification:
- `.venv/bin/python -m pytest tests/test_participant_sheets_gateway.py tests/test_boundaries.py -v` -> 13 passed.
- `.venv/bin/python -m pytest -q` -> 50 passed.

Reviews:
- Code review: `work/participant-core-flows/logs/working/task-2/code-reviewer-1.json`
- Security review: `work/participant-core-flows/logs/working/task-2/security-auditor-1.json`
- Test review: `work/participant-core-flows/logs/working/task-2/test-reviewer-1.json`

Deviations: None.

## Task 3: SQLite dialog state repository

Summary: Added a small SQLite repository for technical dialog state upsert/read/clear using the existing `dialog_states` table only.

Verification:
- `.venv/bin/python -m pytest tests/test_dialog_state_repository.py tests/test_sqlite_schema.py -v` -> 11 passed.
- `.venv/bin/python -m pytest -q` -> 55 passed.

Reviews:
- Code review: `work/participant-core-flows/logs/working/task-3/code-reviewer-1.json`
- Security review: `work/participant-core-flows/logs/working/task-3/security-auditor-1.json`
- Test review: `work/participant-core-flows/logs/working/task-3/test-reviewer-1.json`

Deviations: None.

## Task 4: Participant start and consent service

Summary: Added participant start and consent orchestration with Sheets identity lookup, main-bot user replies, error-bot unknown-user notifications, consent writes, role-aware menus, and SQLite technical dialog state.

Verification:
- `.venv/bin/python -m pytest tests/test_participant_start_flow.py -v` -> 6 passed.
- `.venv/bin/python -m pytest -q` -> 61 passed.

Reviews:
- Code review: `work/participant-core-flows/logs/working/task-4/code-reviewer-1.json`
- Security review: `work/participant-core-flows/logs/working/task-4/security-auditor-1.json`
- Test review: `work/participant-core-flows/logs/working/task-4/test-reviewer-1.json`

Deviations: None.

## Task 5: Read-only participant views

Summary: Added protected menu action handling for goal, planned steps, progress, inert out-of-scope actions, and safe missing-data notifications.

Verification:
- `.venv/bin/python -m pytest tests/test_participant_views.py -v` -> 7 passed.
- `.venv/bin/python -m pytest -q` -> 68 passed.

Reviews:
- Code review: `work/participant-core-flows/logs/working/task-5/code-reviewer-1.json`
- Security review: `work/participant-core-flows/logs/working/task-5/security-auditor-1.json`
- Test review: `work/participant-core-flows/logs/working/task-5/test-reviewer-1.json`

Deviations: None.
