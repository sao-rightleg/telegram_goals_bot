# Decisions Log: insight-flow

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

## Task 1: Insight message and model contracts

Summary: Added insight-flow message contracts, list/full-text formatting helpers, current-week insight models, pagination metadata, and fallback title formatting. No business writes, live SDKs, voice processing, scheduler, PDF, deploy, or production behavior were added.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_messages.py -q` -> 7 passed.
- `.venv/bin/python -m pytest tests/test_participant_messages.py tests/test_weekly_report_messages.py -q` -> 13 passed.
- `.venv/bin/python -m pytest -q` -> 128 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 2: Insight Sheets boundary

Summary: Extended the Sheets gateway protocol and fake implementation with participant-scoped insight list/get operations. Added tests for participant scoping, defensive copies, `insight_title`/`insight_date` row support, and preservation of existing insight append/list behavior.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_sheets_gateway.py -q` -> 4 passed.
- `.venv/bin/python -m pytest tests/test_weekly_report_sheets_gateway.py tests/test_participant_sheets_gateway.py tests/test_boundaries.py -q` -> 18 passed.
- `.venv/bin/python -m pytest -q` -> 132 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 3: Insight draft repository

Summary: Added the SQLite insight draft repository for current-week drafts, ordered text messages, title state, saved/idempotency markers, active draft clearing, and recent saved draft recovery. Extended `draft_insights` with nullable technical fields only; no final business insight storage was added to SQLite.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_draft_repository.py tests/test_sqlite_schema.py -q` -> 13 passed.
- `.venv/bin/python -m pytest tests/test_weekly_report_draft_repository.py tests/test_dialog_state_repository.py -q` -> 11 passed.
- `.venv/bin/python -m pytest -q` -> 139 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 4: Insight menu, add flow, and final save

Summary: Added the adapter-independent insight service for menu, current-week text draft creation, text collection, title validation, skip-title fallback, cancel, voice rejection, final Sheets save, and duplicate finalization handling. Updated participant menu handling so `💡 Мои инсайты` opens the insight menu instead of the generic not-available response.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_participant_views.py -q` -> 16 passed.
- `.venv/bin/python -m pytest tests/test_participant_boundaries.py tests/test_insight_add_flow.py tests/test_participant_views.py -q` -> 21 passed.
- `.venv/bin/python -m pytest -q` -> 148 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 5: Insight list, pagination, and full-text callback

Summary: Added participant-scoped insight listing, newest-first bounded pagination, formatted previews with `читать целиком`, and participant-scoped full-text lookup. Missing or cross-participant callbacks return safe copy and route a technical admin notification without full insight text.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_list_flow.py tests/test_insight_sheets_gateway.py -q` -> 9 passed.
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_insight_list_flow.py tests/test_insight_messages.py tests/test_insight_sheets_gateway.py -q` -> 25 passed.
- `.venv/bin/python -m pytest -q` -> 153 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 6: Insight boundary regression tests

Summary: Added focused insight boundary regressions for captain personal scope, weekly/progress side-effect isolation, deferred voice handling, forbidden runtime dependencies, and safe technical notifications. The tests use fake Sheets, fake bot clients, and temporary SQLite only; no application code changes were needed.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_boundaries.py tests/test_participant_boundaries.py tests/test_weekly_report_boundaries.py -v` -> 16 passed.
- `.venv/bin/python -m pytest -q` -> 158 passed.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 7: Code audit

Summary: Completed the feature code audit and wrote a valid JSON report. The audit found one blocking functional issue: same participant/week `draft_id` and `insight_id` generation prevents the approved unlimited-insights-per-week behavior and needs fixer work.

Verification:
- `.venv/bin/python -m json.tool work/insight-flow/logs/working/task-7/code-audit.json` -> valid JSON.

Reviews:
- None required by this audit task.

Deviations: None.

## Task 8: Security audit

Summary: Completed the security audit and wrote a valid JSON report. The audit found one blocking privacy/storage issue: saved insight drafts retain full personal text in SQLite after final save, which conflicts with the approved storage boundary.

Verification:
- `.venv/bin/python -m json.tool work/insight-flow/logs/working/task-8/security-audit.json` -> valid JSON.

Reviews:
- None required by this audit task.

Deviations: None.

## Task 9: Test audit

Summary: Completed the test audit and wrote a valid JSON report. The audit found three blocking coverage gaps: same-week multiple insights, post-save SQLite full-text cleanup, and insight-specific unknown/no-consent coverage.

Verification:
- `.venv/bin/python -m json.tool work/insight-flow/logs/working/task-9/test-audit.json` -> valid JSON.

Reviews:
- None required by this audit task.

Deviations: None.

## Audit follow-up: Resolve insight audit blockers

Summary: Resolved the code, security, and test audit blockers by allowing multiple current-week insights per participant, deriving unique full-text callback ids from unique draft ids, purging full draft text from SQLite after successful save, and adding direct unknown/no-consent insight service regressions. Audit JSON reports were updated with resolution metadata.

Verification:
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_insight_draft_repository.py -q` -> 18 passed.
- `.venv/bin/python -m pytest tests/test_insight_add_flow.py tests/test_insight_boundaries.py tests/test_insight_draft_repository.py tests/test_insight_list_flow.py tests/test_insight_messages.py tests/test_insight_sheets_gateway.py tests/test_participant_boundaries.py tests/test_participant_views.py -q` -> 51 passed.
- `.venv/bin/python -m pytest -q` -> 161 passed.
- `.venv/bin/python -m json.tool work/insight-flow/logs/working/task-7/code-audit.json >/tmp/code-audit.json && .venv/bin/python -m json.tool work/insight-flow/logs/working/task-8/security-audit.json >/tmp/security-audit.json && .venv/bin/python -m json.tool work/insight-flow/logs/working/task-9/test-audit.json >/tmp/test-audit.json` -> valid JSON.

Reviews:
- Not run in this session because reviewer subagents require explicit user request for delegation.

Deviations: None.

## Task 10: Pre-deploy QA

Summary: Pre-deploy QA passed. Full local pytest suite is green, all user-spec and tech-spec acceptance criteria are verified, audit reports exist with zero unresolved blocking issues, and no deploy/live environment action was performed.

Verification:
- `.venv/bin/python -m pytest -q` -> 161 passed.
- `.venv/bin/python -m json.tool work/insight-flow/logs/working/task-10/pre-deploy-qa.json` -> valid JSON.
- Full report: `work/insight-flow/logs/working/task-10/pre-deploy-qa.json`.

Reviews:
- None required by this QA task.

Deviations: None.
