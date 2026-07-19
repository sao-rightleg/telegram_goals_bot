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

## Task 10a: Test audit fixes

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Closed both blocking test-audit gaps by adding direct live Telegram `getUpdates` adapter tests and a startup readiness failure notification test that verifies sanitized error-bot delivery. The remaining workflow YAML/shell validation note is documented as non-blocking hardening.
**Deviations:** None.

**Reviews:**

Not run. This task fixes findings from the completed test audit.

**Verification:**
- `python -m pytest tests/test_boundaries.py tests/test_runtime_entrypoint.py -v` -> 33 passed
- `python -m pytest -q` -> 351 passed

## Task 11: Pre-deploy QA

**Status:** Done
**Commit:** this commit
**Agent:** main agent
**Summary:** Pre-deploy QA passed. Full local pytest passed with 351 tests, targeted runtime/config/deploy smoke passed with 71 tests, and dependency audit found no known vulnerabilities. Acceptance mapping covered 36 criteria: 31 passed locally, 0 failed, and 5 live checks were deferred to post-deploy verification.
**Deviations:** None.

**Reviews:**

None.

**Verification:**
- `python -m pytest -v` -> 351 passed in 16.76s
- `python -m pytest tests/test_config.py tests/test_boundaries.py tests/test_voice_processing_boundaries.py tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> 71 passed in 3.11s
- `uv tool run pip-audit -r <generated requirements from pyproject>` -> No known vulnerabilities found
- `python -m json.tool work/live-runtime-integration/logs/working/pre-deploy-qa.json >/tmp/pre-deploy-qa.pretty.json` -> OK
- Full report: `work/live-runtime-integration/logs/working/pre-deploy-qa.json`

**Deferred to post-deploy:** Five criteria require live verification: test VPS launch, real Yandex voice, interactive Telegram smoke, captain smoke, and test Google Sheet data.

## Task 12: Deploy test-live

**Status:** Blocked
**Commit:** not completed
**Agent:** main agent
**Summary:** Test-live deployment was approved and started through GitHub Actions run `29183251404` for ref `c174fd2fd7d38b1b5c549bf256419664105142e1`. The workflow passed checkout, Python setup, runner tests, test secret validation, archive creation, and SSH setup, then failed at `Upload archive` before install/restart. The sanitized error is `Load key "/home/runner/.ssh/deploy_key": error in libcrypto` followed by SSH permission denial, indicating the test deploy private key secret is malformed/unreadable or does not match the VPS authorized key.
**Deviations:** None.

**Reviews:**

None.

**Verification:**
- `gh workflow run "Deploy Test" --repo sao-rightleg/telegram_goals_bot --ref main -f ref=c174fd2fd7d38b1b5c549bf256419664105142e1` -> run `29183251404` started
- `gh run view 29183251404 --repo sao-rightleg/telegram_goals_bot` -> failed at `Upload archive`
- `gh run view 29183251404 --repo sao-rightleg/telegram_goals_bot --log-failed` -> sanitized SSH key load failure and permission denial
- Deploy log: `work/live-runtime-integration/logs/working/deploy-test.md`

**External actions:** GitHub Actions `Deploy Test` workflow was started. No direct SSH/VPS access, live Telegram/Google/Yandex smoke, production workflow, production service, production secrets, or production app directory action was performed.

**Retry 2026-07-12:** After the user updated `TEST_VPS_SSH_KEY`, reran `Deploy Test` as run `29183791812` for the same ref. It failed again at `Upload archive` with the same sanitized `Load key "/home/runner/.ssh/deploy_key": error in libcrypto` error, so the blocker remains the private key secret format/content.

**Retry 2026-07-12 via gh secret update:** The user reported updating `TEST_VPS_SSH_KEY` through `gh`. Local key file `~/.ssh/telegram_goals_bot_test` validates with `ssh-keygen -y`, but run `29202403697` still failed at `Upload archive` with the same `error in libcrypto`. GitHub environment secret metadata shows `TEST_VPS_SSH_KEY updated_at: 2026-07-12T17:34:44Z`. Next safest fix is setting the environment secret directly from this workspace with `gh secret set ... --body-file`.

**Retry 2026-07-12 secret set from workspace:** With user approval, updated `TEST_VPS_SSH_KEY` from `~/.ssh/telegram_goals_bot_test` via `gh secret set ... < file`, then reran `Deploy Test` as run `29202529683`. The SSH/upload blocker is fixed: archive upload passed, remote install started, and VPS tests passed with `351 passed in 15.41s`. The run now fails at `check-config` because `/opt/telegram_goals_bot_test/shared/.env` is missing required runtime settings: `MAIN_TELEGRAM_BOT_TOKEN`, `ERROR_TELEGRAM_BOT_TOKEN`, `NOTIFICATION_TELEGRAM_BOT_TOKEN`, `GOOGLE_SHEETS_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `ADMIN_TELEGRAM_ID`, `ADMIN_ERROR_CHAT_ID`, `SITNIKOV_TELEGRAM_ID`, `SQLITE_DB_PATH`, `AUDIO_STORAGE_DIR`, and `PDF_STORAGE_DIR`.

**Retry 2026-07-19 credentials configured:** After the user configured Google credentials, reran `Deploy Test` as run `29697217640`. The workflow again passed upload, remote install, and VPS tests (`351 passed in 15.99s`). `check-config` now fails on `TRANSCRIPTION_PROVIDER`: it must be one of `fake` or `yandex`. For test-live without Yandex credentials, set `TRANSCRIPTION_PROVIDER=fake` in `/opt/telegram_goals_bot_test/shared/.env`.
