---
status: planned
depends_on: [1, 2, 3, 4, 5]
wave: 3
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 6: Runtime composition and readiness

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Replace the current `RuntimeNotImplementedError` path with runtime composition and a controlled polling runtime. This task wires the live adapters from earlier tasks to repositories, services, notification router, storage policy, and the dispatcher from Task 5.

The result should make `telegram-goals-bot run` start the test-live runtime with valid config while preserving readiness behavior for `check-config` and `init-storage`.

## What to do

- Add composition code that creates live Telegram clients/downloader, Google Sheets gateway, Yandex transcriber, repositories, notification router, and business services.
- Extend readiness checks to validate local storage, provider config, Google credentials path, Google Sheets access/schema, and adapter construction.
- Replace `run_bot()` not-implemented behavior with a polling loop that calls the dispatcher.
- Add graceful shutdown behavior suitable for systemd.
- Add a controlled fake polling mode or injectable polling runner for automated tests.
- Keep `check-config` non-destructive beyond storage initialization and schema/readiness validation.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_runtime_entrypoint.py::test_run_bot_no_longer_raises_not_implemented_with_fake_runtime` - controlled runtime starts/stops.
- `tests/test_runtime_entrypoint.py::test_check_config_runs_google_schema_validation` - readiness invokes schema validator.
- `tests/test_runtime_entrypoint.py::test_run_bot_composes_three_bot_router_and_services` - composition creates expected collaborators.
- `tests/test_project_tooling.py::test_runtime_does_not_reference_runtime_not_implemented_error_path` - stale blocker is gone or not used by `run`.

## Acceptance Criteria

- [ ] `telegram-goals-bot run` no longer raises `RuntimeNotImplementedError` for valid test-live config.
- [ ] Runtime composition wires all live adapters and existing services.
- [ ] `check-config` validates Google Sheets schema fail-fast.
- [ ] Runtime startup reports sanitized admin error when startup readiness fails after error bot is available.
- [ ] Automated tests can run without real Telegram, Google, or Yandex secrets.
- [ ] Storage initialization behavior remains compatible with existing tests.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/config.py](/root/telegram_goals_bot/app/config.py)
- [app/storage/sqlite.py](/root/telegram_goals_bot/app/storage/sqlite.py)
- [app/services/notifications.py](/root/telegram_goals_bot/app/services/notifications.py)
- [app/storage/weekly_report_drafts.py](/root/telegram_goals_bot/app/storage/weekly_report_drafts.py)
- [app/storage/insight_drafts.py](/root/telegram_goals_bot/app/storage/insight_drafts.py)
- [app/storage/dialog_state.py](/root/telegram_goals_bot/app/storage/dialog_state.py)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)
- [tests/test_project_tooling.py](/root/telegram_goals_bot/tests/test_project_tooling.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> all pass

## Details

**Files:**
- `app/runtime.py` - add composition/readiness/polling wiring and remove the live runtime blocker.
- `tests/test_runtime_entrypoint.py` - add fake-runtime composition and readiness tests.
- `tests/test_project_tooling.py` - add stale-blocker/static runtime checks if useful.

**Dependencies:** Tasks 1-5.

**Edge cases:**
- Google schema validation fails before polling starts.
- Error bot token exists but startup readiness fails.
- Polling loop receives transient Telegram API error.
- Process receives shutdown signal.
- `check-config` must not start polling.

**Implementation hints:**
- Keep construction injectable so tests can pass fake adapters and a one-shot polling runner.
- Keep runtime errors sanitized before printing or notifying admin.
- Avoid adding scheduler/report live execution to this task.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-6/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-6/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-6/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
