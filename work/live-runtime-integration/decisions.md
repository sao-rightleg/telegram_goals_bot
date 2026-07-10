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
