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

## Task 4: Weekly report voice integration

**Status:** Done
**Commit:** 22c265d
**Agent:** main agent
**Summary:** Connected weekly report voice handling through an optional `VoiceMessageService` dependency while preserving deadline, duplicate, selected-step, and finalization ownership in `WeeklyReportService`. Final weekly report rows now include ordered report text plus `transcription_text`, `audio_file_path`, and `audio_deleted_at` fields derived from accepted draft voice attachments.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation. The legacy `reject_voice_message` method remains as a fallback when the voice dependency is not wired, while the new weekly voice entrypoint uses `add_voice_message`.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_weekly_report_finalize.py::test_voice_report_final_save_includes_transcription_and_audio_path tests/test_weekly_report_finalize.py::test_mixed_text_and_voice_report_preserves_order tests/test_weekly_report_boundaries.py::test_voice_does_not_bypass_deadline_or_duplicate_guards -q` → 3 passed
- `.venv/bin/python -m pytest tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py tests/test_voice_processing_service.py -q` → 23 passed
- `.venv/bin/python -m pytest -q` → 176 passed
- `git diff --check` → OK

## Task 5: Insight voice integration

**Status:** Done
**Commit:** b281f94
**Agent:** main agent
**Summary:** Connected insight voice handling through an optional `VoiceMessageService` dependency while keeping final business writes in `InsightService`. Final insight rows now include ordered insight text plus `transcription_text`, `audio_file_path`, and `audio_deleted_at` from accepted draft voice attachments, with weekly report/status data left unchanged.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation. The legacy `reject_voice_message` method remains as a fallback when the voice dependency is not wired, while the new insight voice entrypoint uses `add_voice_message`.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py::test_voice_insight_final_save_includes_transcription_and_audio_path tests/test_insight_add_flow.py::test_mixed_text_and_voice_insight_preserves_order tests/test_insight_boundaries.py::test_voice_insight_does_not_change_weekly_status_or_progress tests/test_insight_draft_repository.py::test_saved_insight_draft_purges_voice_transcription_text -q` → 4 passed
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_insight_boundaries.py tests/test_voice_processing_service.py -q` → 25 passed
- `.venv/bin/python -m pytest -q` → 179 passed
- `git diff --check` → OK

## Task 6: Voice boundary regression coverage

**Status:** Done
**Commit:** eda2f42
**Agent:** main agent
**Summary:** Added cross-flow voice boundary regressions for mixed text/voice ordering, over-limit no-side-effect behavior, admin-only failure routing, unsafe audio path fragments, and gitignored audio/secret artifact assumptions. No application code changes were needed because the current implementation already satisfied these regressions.
**Deviations:** Formal reviewer subagents were not run because the current tool policy requires explicit user permission for delegation. The TDD anchors passed immediately after adding tests, so this task remained pure regression coverage instead of exposing an implementation gap.

**Reviews:**

*Round 1:*
- code-reviewer: Not run → subagent delegation not explicitly requested for this task execution.
- security-auditor: Not run → subagent delegation not explicitly requested for this task execution.
- test-reviewer: Not run → subagent delegation not explicitly requested for this task execution.

**Verification:**
- `.venv/bin/python -m pytest tests/test_voice_processing_boundaries.py::test_mixed_text_and_voice_ordering_across_flows tests/test_voice_processing_boundaries.py::test_over_limit_voice_has_no_side_effects tests/test_voice_processing_boundaries.py::test_voice_failure_routes_only_to_admin_error_chat tests/test_storage_paths.py::test_audio_path_rejects_unsafe_voice_fragments -q` → 4 passed
- `.venv/bin/python -m pytest tests/test_voice_processing_boundaries.py tests/test_boundaries.py tests/test_storage_paths.py -q` → 16 passed
- `.venv/bin/python -m pytest -q` → 184 passed
- `git diff --check` → OK

## Task 7: Code Audit

**Status:** Done
**Commit:** f2869d3
**Agent:** main agent
**Summary:** Completed full-feature code audit for voice-processing implementation and tests. The report lists 1 blocking major finding about saved voice insight display using voice-only transcription, plus 1 non-blocking minor finding about failed attachment metadata observability.
**Deviations:** None.

**Reviews:**

*Round 1:*
- code-reviewer: Not applicable → Task 7 is the code audit report.

**Verification:**
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-7/code-audit.json` → valid JSON

## Task 8: Security Audit

**Status:** Done
**Commit:** 6049828
**Agent:** main agent
**Summary:** Completed full-feature security audit for voice-processing. The report lists 1 blocking medium finding: failed voice processing can leave a downloaded local audio file without failed attachment metadata or deletion, creating a sensitive-data retention risk.
**Deviations:** None.

**Reviews:**

*Round 1:*
- security-auditor: Not applicable → Task 8 is the security audit report.

**Verification:**
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-8/security-audit.json` → valid JSON

## Task 9: Test Audit

**Status:** Done
**Commit:** 5a34352
**Agent:** main agent
**Summary:** Completed full-feature test audit for voice-processing unit, integration, and boundary tests. The report lists 2 blocking test gaps: missing saved mixed voice insight display regression and missing failed-downloaded-audio retention/metadata regression.
**Deviations:** None.

**Reviews:**

*Round 1:*
- test-reviewer: Not applicable → Task 9 is the test audit report.

**Verification:**
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-9/test-audit.json` → valid JSON

## Task 10: Pre-deploy QA

**Status:** Done
**Commit:** 892eb33
**Agent:** main agent
**Summary:** Pre-deploy QA completed with failed release readiness. Full local pytest passed (`184 passed`), audit JSON reports are valid, and no deploy/live environment action was performed. Release gate is blocked by unresolved findings CA-001, SA-001, TA-001, and TA-002.
**Deviations:** None.

**Reviews:**

*Round 1:*
- pre-deploy-qa: Not applicable → Task 10 is the pre-deploy QA report.

**Verification:**
- `.venv/bin/python -m pytest -q` → 184 passed
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-7/code-audit.json` → valid JSON
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-8/security-audit.json` → valid JSON
- `.venv/bin/python -m json.tool work/voice-processing/logs/working/task-9/test-audit.json` → valid JSON
- `git diff --check` → OK
- `git status --short` → no generated audio, SQLite databases, credentials, or secrets staged before QA edits
- Full report: `work/voice-processing/logs/working/task-10/pre-deploy-qa.json`
