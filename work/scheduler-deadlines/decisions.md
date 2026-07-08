# Decisions Log: scheduler-deadlines

Agent reports on completed tasks. Each entry is written by the agent that executed the task.

---

## Task 1: Scheduler Copy and Result Contracts

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added approved Russian scheduler reminder copy, silent participant notification formatting, and scheduler result/data contracts for later jobs. Sunday 18:00 copy is reminder-only and does not expose report status buttons or internal IDs.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_messages.py tests/test_weekly_report_messages.py -q` -> 8 passed

## Task 2: Scheduler Sheets Gateway Queries

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Extended the Sheets gateway protocol and fake implementation with scheduler participant, team, and tracker read paths. New fake rows are copied on read so scheduler tests cannot mutate internal gateway state.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_sheets_gateway.py tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py -q` -> 18 passed

## Task 3: Scheduler SQLite Repository

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added a scheduler SQLite repository for job runs, reminder retry state, and technical error recording. Added `attempt_count` to `reminder_log` as technical state so reminder retry limits can be enforced without storing business facts in SQLite.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_repository.py tests/test_sqlite_schema.py -q` -> 14 passed

## Task 4: Reminder Job Service

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added `SchedulerService.run_reminder` with Yekaterinburg week selection, Sheets-based recipient filtering, main-bot participant delivery, SQLite reminder logging, participant-scoped retry, and admin error notification after retry exhaustion.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_deadlines.py tests/test_scheduler_repository.py tests/test_scheduler_messages.py -q` -> 13 passed

## Task 5: Week Close Service

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added idempotent `SchedulerService.close_week` that creates system deadline gray weekly reports for active participants without finalized reports. The implementation skips dropped participants, preserves unfinished drafts, and can recover from partial Sheets append failures by rerunning.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_deadlines.py tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py -q` -> 29 passed

## Task 6: Silent Participant Notifications

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added team-scoped silent participant notifications after week close. Notifications are aggregated for captain/tracker recipients, omit draft state, and missing recipient chat ids produce admin errors without blocking gray report creation.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local tests and diff review were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_deadlines.py tests/test_scheduler_messages.py tests/test_scheduler_sheets_gateway.py tests/test_scheduler_repository.py -q` -> 27 passed

## Task 7: Scheduler Boundary and Regression Coverage

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added an acceptance-criteria coverage matrix for scheduler deadlines and verified the scheduler, SQLite-adjacent, weekly report finalization, and deadline boundary regression suite. Existing late/duplicate weekly report behavior remains unchanged.
**Deviations:** Review subagents were not launched because this environment only permits delegation after an explicit agent request; local test review and smoke verification were used for this task.

**Reviews:**

*Round 1:*
- local review: OK

**Verification:**
- `.venv/bin/python -m pytest tests/test_scheduler_foundation.py tests/test_scheduler_deadlines.py tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py -v` -> 40 passed
- `.venv/bin/python -m pytest tests/test_scheduler_foundation.py tests/test_scheduler_deadlines.py tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py` -> 40 passed

## Task 8: Code Audit

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Completed a full-feature code audit and wrote `work/scheduler-deadlines/logs/working/task-8/code-audit.json`. The audit found one major reminder idempotency issue and one minor admin-error best-effort concern.
**Deviations:** None.

**Reviews:**

*Round 1:*
- local audit: 2 findings -> `work/scheduler-deadlines/logs/working/task-8/code-audit.json`

**Verification:**
- `.venv/bin/python -m json.tool work/scheduler-deadlines/logs/working/task-8/code-audit.json` -> valid JSON

<!-- Entries are added by agents as tasks are completed.

Format is strict — use only these sections, do not add others.
Do not include: file lists, findings tables, JSON reports, step-by-step logs.
Review details — in JSON files via links. QA report — in logs/working/.

## Task N: [title]

**Status:** Done
**Commit:** abc1234
**Agent:** [teammate name or "main agent"]
**Summary:** 1-3 sentences: what was done, key decisions. Not a file list.
**Deviations:** None / Deviated from spec: [reason], did [what].

**Reviews:**

*Round 1:*
- code-reviewer: 2 findings → [logs/working/task-N/code-reviewer-1.json]
- security-auditor: OK → [logs/working/task-N/security-auditor-1.json]

*Round 2 (after fixes):*
- code-reviewer: OK → [logs/working/task-N/code-reviewer-2.json]

**Verification:**
- `npm test` → 42 passed
- Manual check → OK

-->
