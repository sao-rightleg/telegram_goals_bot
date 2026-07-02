# Decisions Log: mvp-foundation

Agent reports on completed tasks. Each entry is written by the agent that executed the task.

---

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

## Task 1: Python package and test tooling

**Status:** Done
**Commit:** bd89b30
**Agent:** main agent
**Summary:** Added minimal Python project metadata, pytest discovery configuration, importable `app` package modules, and smoke tests for package imports, pytest wiring, and forbidden infrastructure dependencies. Kept runtime dependencies empty and added generated Python package metadata to `.gitignore`.
**Deviations:** Formal reviewer sub-agents were not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- infrastructure-reviewer: Not run → multi-agent review not started in current execution mode.
- test-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest -v` → 3 passed
- `source .venv/bin/activate && python -c "import app; print('ok')"` → ok
- `git diff --check` → OK

## Task 2: Settings and secret redaction

**Status:** Done
**Commit:** f499d8e
**Agent:** main agent
**Summary:** Added typed settings loading from process environment or optional `.env`, strict validation for the three Telegram bot tokens and core MVP settings, secret redaction helpers, and logging setup that accepts redacted settings metadata. Kept timezone out of runtime configuration.
**Deviations:** Formal reviewer sub-agents were not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → multi-agent review not started in current execution mode.
- security-auditor: Not run → multi-agent review not started in current execution mode.
- test-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest tests/test_config.py -v` → 10 passed
- `source .venv/bin/activate && python -m pytest -v` → 13 passed
- `git diff --check` → OK

## Task 3: SQLite technical-state schema

**Status:** Done
**Commit:** bec97a1
**Agent:** main agent
**Summary:** Added SQLite technical-state schema initialization and inspection helpers using the standard library. The schema creates draft, dialog, scheduler, reminder, and error technical tables with primary keys, unique/idempotency constraints, lookup indexes, practical checks, and draft-owner triggers while excluding business-primary tables.
**Deviations:** Formal reviewer sub-agents were not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → multi-agent review not started in current execution mode.
- security-auditor: Not run → multi-agent review not started in current execution mode.
- test-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest tests/test_sqlite_schema.py -v` → 6 passed
- `source .venv/bin/activate && python -m pytest -v` → 19 passed
- `git diff --check` → OK

## Task 4: Scheduler and file-storage foundations

**Status:** Done
**Commit:** pending
**Agent:** main agent
**Summary:** Added executable scheduler calendar constants for the approved Yekaterinburg timezone, challenge dates, reminder schedule, and idempotency keys. Added local storage path policies for audio, SQLite, PDFs, and backups with retention constants and safeguards against URL/path traversal fragments.
**Deviations:** Formal reviewer sub-agents were not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → multi-agent review not started in current execution mode.
- test-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest tests/test_scheduler_foundation.py tests/test_storage_paths.py -v` → 10 passed
- `source .venv/bin/activate && python -m pytest -v` → 29 passed
- `git diff --check` → OK
