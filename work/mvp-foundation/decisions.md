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
**Commit:** cfd7607
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

## Task 5: External integration boundaries

**Status:** Done
**Commit:** 89fff28
**Agent:** main agent
**Summary:** Added boundary protocols and fake implementations for Google Sheets, three Telegram bot clients, notification routing, report generation, and speech transcription. Technical errors route only through the error bot boundary, report/speech fakes reuse the Task 4 storage path policy, and boundary modules avoid live SDK imports.
**Deviations:** Formal reviewer sub-agents were not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → multi-agent review not started in current execution mode.
- security-auditor: Not run → multi-agent review not started in current execution mode.
- test-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest tests/test_boundaries.py -v` → 6 passed
- `source .venv/bin/activate && python -m pytest -v` → 35 passed
- `git diff --check` → OK

## Task 6: Foundation documentation and smoke commands

**Status:** Done
**Commit:** 2d8226a
**Agent:** main agent
**Summary:** Updated README with the current foundation status, local setup/test commands, smoke checks, and explicit scope boundaries: no production deploy, full Telegram flows, live API integrations, voice transcription, or PDF generation are included in the foundation feature.
**Deviations:** Formal documentation-reviewer sub-agent was not spawned because the user did not explicitly request multi-agent execution in this turn; local verification was completed.

**Reviews:**

*Round 1:*
- documentation-reviewer: Not run → multi-agent review not started in current execution mode.

**Verification:**
- `source .venv/bin/activate && python -m pytest -v` → 35 passed
- `source .venv/bin/activate && python -m pytest` → 35 passed
- `source .venv/bin/activate && python -c "import app; print('ok')"` → ok
- `git diff --check` → OK

## Task 7: Code Audit

**Status:** Done
**Commit:** pending
**Agent:** main agent
**Summary:** Reviewed foundation source, tests, and README for code quality, module boundaries, shared-resource ownership, and scope creep. The audit passed with no blocking findings; report written to `work/mvp-foundation/logs/working/task-7/code-audit.json`.
**Deviations:** None.

**Reviews:**

*Round 1:*
- code-audit: passed → `work/mvp-foundation/logs/working/task-7/code-audit.json`

**Verification:**
- `test -f work/mvp-foundation/logs/working/task-7/code-audit.json` → OK
- `python3 -m json.tool work/mvp-foundation/logs/working/task-7/code-audit.json` → OK

## Task 8: Security Audit

**Status:** Done
**Commit:** pending
**Agent:** main agent
**Summary:** Reviewed settings, logging, SQLite schema, storage paths, notification routing, and tests for secret leakage, unsafe paths, business-data storage drift, and unauthorized technical-error routing. The audit passed with no blocking findings; low residual hardening notes are documented in `work/mvp-foundation/logs/working/task-8/security-audit.json`.
**Deviations:** None.

**Reviews:**

*Round 1:*
- security-audit: passed → `work/mvp-foundation/logs/working/task-8/security-audit.json`

**Verification:**
- `test -f work/mvp-foundation/logs/working/task-8/security-audit.json` → OK
- `python3 -m json.tool work/mvp-foundation/logs/working/task-8/security-audit.json` → OK

## Task 9: Test Audit

**Status:** Done
**Commit:** pending
**Agent:** main agent
**Summary:** Reviewed all foundation tests for meaningful assertions, negative cases, production-secret isolation, and coverage of config, redaction, SQLite, scheduler, storage, and boundary behavior. The audit passed with one low-severity smoke-test improvement noted in `work/mvp-foundation/logs/working/task-9/test-audit.json`.
**Deviations:** None.

**Reviews:**

*Round 1:*
- test-audit: passed → `work/mvp-foundation/logs/working/task-9/test-audit.json`

**Verification:**
- `test -f work/mvp-foundation/logs/working/task-9/test-audit.json` → OK
- `python3 -m json.tool work/mvp-foundation/logs/working/task-9/test-audit.json` → OK
