# Decisions Log: live-runtime-integration

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

## Task 1: Runtime configuration and provider selection

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added typed transcription and Telegram runtime settings, including `TRANSCRIPTION_PROVIDER=yandex` validation, Yandex timeout/poll settings, Telegram polling/request settings, and redaction for transcription API keys and key paths. Updated `.env.example` with variable names/default numeric values only.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_config.py tests/test_runtime_entrypoint.py -v` -> 24 passed
- `git diff --check` -> OK
- `python -m pytest -v` -> 311 passed

## Task 2: Live Telegram Bot API clients

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added concrete Telegram Bot API message/document clients and file downloader behind the existing bot boundaries. The live adapters use injectable `httpx` clients for testability and sanitize bot tokens in Telegram API errors.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_boundaries.py -v` -> 11 passed
- `git diff --check` -> OK
- `python -m pytest -v` -> 315 passed

## Task 3: Google Sheets adapter and schema validation

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added a live Google Sheets gateway implementing the existing `SheetsGateway` contract with header-based row mapping, append/update operations, required schema validation, and compatibility aliases for current service keys versus documented Sheets headers. Added fake Google service tests for participant, weekly report, insight, report-read, and schema validation behavior.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py tests/test_insight_sheets_gateway.py tests/test_reports_sheets_gateway.py -v` -> 31 passed
- `git diff --check` -> OK
- `python -m pytest -v` -> 323 passed

## Task 4: Yandex SpeechKit transcriber

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added a synchronous `YandexSpeechKitTranscriber` behind the existing `SpeechTranscriber` protocol. It submits local OGG Opus audio to SpeechKit v3, polls a bounded operation timeout, reads recognition results, and maps timeout, HTTP, failed-operation, empty-result, missing-file, and invalid-config cases to sanitized `YandexSpeechKitError` exceptions.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_voice_processing_service.py tests/test_voice_processing_boundaries.py -v` -> 13 passed
- `git diff --check` -> OK
- `python -m pytest -q` -> 326 passed

## Task 5: Telegram update parsing and dispatcher

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added Telegram update DTO parsing and a runtime dispatcher surface that routes `/start`, consent/menu/action callbacks, active weekly/insight/captain text, and weekly/insight voice metadata into existing services. Added stable callback constants and sanitized malformed-callback admin notifications without including raw callback payloads.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_runtime_entrypoint.py -v` -> 10 passed
- `python -m pytest tests/test_participant_start_flow.py tests/test_weekly_report_start_flow.py tests/test_insight_add_flow.py tests/test_captain_team_flow.py tests/test_captain_manual_report_flow.py tests/test_runtime_entrypoint.py -v` -> 49 passed
- `python -m pytest tests/test_participant_start_flow.py tests/test_weekly_report_start_flow.py tests/test_insight_add_flow.py tests/test_captain_team_flow.py tests/test_captain_manual_report_flow.py -v` -> 39 passed
- `git diff --check` -> OK
- `python -m pytest -q` -> 332 passed

## Task 6: Runtime composition and readiness

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Replaced the not-implemented runtime path with live runtime composition for Telegram bots, Google Sheets, Yandex/fake transcription, SQLite repositories, notification routing, voice service, business services, dispatcher, and a controlled Telegram polling runner. Added readiness validation for Google credentials, Google Sheets schema, provider construction, and sanitized startup readiness admin notifications.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> 18 passed
- `git diff --check` -> OK
- `python -m pytest -q` -> 336 passed

## Task 7: Test-live deployment pipeline

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Added a manual-only `Deploy Test` GitHub Actions workflow using GitHub environment `test`, test-scoped VPS secrets, `/opt/telegram_goals_bot_test`, and `telegram-goals-bot-test.service`. Added the test systemd unit, deployment documentation, and static tooling tests that guard against production app-dir/service references in test deploy artifacts.
**Deviations:** None.

**Reviews:**

Not run. Reviewer subagents require explicit user request in this runtime.

**Verification:**
- `python -m pytest tests/test_project_tooling.py -v` -> 8 passed
- `git diff --check` -> OK
- `python -m pytest -q` -> 339 passed

## Task 8: Code Audit

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Completed holistic code audit for Tasks 1-7 and saved `logs/working/code-audit.json`. The audit found three blocking live-runtime readiness issues: missing outbound Telegram reply markup/callback delivery, missing polling error containment and handled-offset policy, and uncaught non-ConfigurationError readiness failures in `check-config`.
**Deviations:** None.

**Reviews:**

None.

**Verification:**
- `python -m json.tool work/live-runtime-integration/logs/working/code-audit.json >/tmp/code-audit.pretty.json` -> OK
- `test -s work/live-runtime-integration/logs/working/code-audit.json` -> OK

## Task 8a: Code audit fixes

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Fixed the three blocking audit findings by preserving service response buttons/menu items through the Telegram outbound boundary, adding sanitized polling error containment with handled-offset advancement, and normalizing Google Sheets readiness failures into clear CLI errors. Callback data is generated from stable constants for consent, role menus, weekly status buttons, and insight buttons.
**Deviations:** None.

**Reviews:**

Not run. This task fixes findings from the completed code audit.

**Verification:**
- `python -m pytest tests/test_boundaries.py tests/test_runtime_entrypoint.py -v` -> 29 passed
- `python -m pytest -q` -> 344 passed

## Task 9: Security Audit

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Completed security/privacy audit for live runtime integration and saved `logs/working/security-audit.json`. The audit found two blocking medium findings before test-live deploy: vulnerable pytest dev dependency resolution in the deploy path and runtime storage permissions depending on VPS umask; it also found one non-blocking low SSH host-key pinning issue.
**Deviations:** None.

**Reviews:**

None.

**Verification:**
- `python -m json.tool work/live-runtime-integration/logs/working/security-audit.json >/tmp/security-audit.pretty.json` -> OK
- `uv tool run pip-audit -r <generated requirements from pyproject> --format json` -> 1 known vulnerability found in pytest

## Task 9a: Security audit fixes

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Fixed the two blocking security audit findings by raising the dev pytest constraint to the fixed major line and enforcing private permissions for runtime storage directories, the SQLite database file, test-live shared directories, and the test systemd umask. The low SSH host-key pinning finding remains documented as non-blocking hardening for a later deploy pipeline pass.
**Deviations:** None.

**Reviews:**

Not run. This task fixes findings from the completed security audit.

**Verification:**
- `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> 28 passed
- `uv tool run pip-audit -r <generated requirements from pyproject>` -> No known vulnerabilities found
- `python -m pytest -q` -> 348 passed

## Task 10: Test Audit

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Completed test coverage/quality audit for live runtime integration and saved `logs/working/test-audit.json`. The audit found two blocking high-severity coverage gaps before final QA: missing direct tests for the live Telegram `getUpdates` adapter and missing tests for startup readiness failure notification via the error bot; one low non-blocking workflow static-test limitation remains documented.
**Deviations:** None.

**Reviews:**

None.

**Verification:**
- `python -m pytest tests/test_config.py tests/test_boundaries.py tests/test_voice_processing_boundaries.py tests/test_voice_processing_service.py tests/test_runtime_entrypoint.py tests/test_project_tooling.py tests/test_participant_sheets_gateway.py tests/test_weekly_report_sheets_gateway.py tests/test_insight_sheets_gateway.py tests/test_reports_sheets_gateway.py -q` -> 105 passed
- `python -m json.tool work/live-runtime-integration/logs/working/test-audit.json >/tmp/test-audit.pretty.json` -> OK
