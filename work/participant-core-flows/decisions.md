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
