# Decisions Log: voice-processing

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

## Task 1: Voice message contracts and Telegram file boundary

**Status:** Done
**Commit:** f538239
**Agent:** main agent
**Summary:** Added adapter-independent voice input contracts, approved Russian voice-processing copy, and a fake Telegram file downloader boundary. Kept implementation local/fake-only with no live SDK imports and added TDD coverage for copy, metadata contracts, fake downloads, and boundary import safety.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation; local TDD, smoke, and full-suite verification were completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_boundaries.py tests/test_voice_processing_messages.py -q` → 9 passed
- `.venv/bin/python -m pytest tests/test_boundaries.py tests/test_weekly_report_messages.py tests/test_insight_messages.py tests/test_voice_processing_messages.py -q` → 21 passed
- `.venv/bin/python -m pytest -q` → 164 passed
- `git diff --check` → OK

## Task 2: Draft attachment repository operations

**Status:** Done
**Commit:** 7839662
**Agent:** main agent
**Summary:** Added weekly report and insight draft repository operations for accepted voice transcriptions, storing technical attachment metadata and ordered `voice_transcription` draft messages. Saved insight cleanup now deletes voice attachment rows together with draft messages so personal transcription text is purged after save.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation; local TDD, smoke, and full-suite verification were completed.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py::test_append_voice_transcription_preserves_order tests/test_weekly_report_draft_repository.py::test_append_voice_attachment_stores_metadata tests/test_insight_draft_repository.py::test_append_voice_transcription_preserves_order tests/test_insight_draft_repository.py::test_saved_insight_draft_purges_voice_transcription_text -q` → 4 passed
- `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py tests/test_insight_draft_repository.py tests/test_sqlite_schema.py -q` → 23 passed
- `.venv/bin/python -m pytest -q` → 168 passed
- `git diff --check` → OK

## Task 3: Voice processing service

**Status:** Done
**Commit:** 2d95e2c
**Agent:** main agent
**Summary:** Implemented `VoiceMessageService` to route active weekly report and insight voice messages through dialog state, local audio path policy, Telegram file download, transcription, draft append operations, and admin-only technical failure notifications. Added focused service tests for no active draft, over-limit rejection, weekly/insight success, and transcription failure preserving existing draft content.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation. Insight voice paths use the safe technical slug `personal_insights` because insight draft state does not carry team metadata and the service stays scoped to technical draft state instead of adding a Sheets dependency.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_voice_processing_service.py -q` → 5 passed
- `.venv/bin/python -m pytest tests/test_voice_processing_service.py tests/test_voice_processing_messages.py tests/test_boundaries.py tests/test_weekly_report_draft_repository.py tests/test_insight_draft_repository.py -q` → 30 passed
- `.venv/bin/python -m pytest -q` → 173 passed
- `git diff --check` → OK
