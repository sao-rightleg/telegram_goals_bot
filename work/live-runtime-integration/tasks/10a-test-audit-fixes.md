---
status: done
depends_on: [10]
wave: 5
skills: [code-writing, test-master]
verify: [smoke]
reviewers: []
teammate_name:
---

# Task 10a: Test audit fixes

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)
- `/skill:test-master` - [SKILL.md](/root/.codex/skills/test-master/SKILL.md)

## Description

Fix the blocking test coverage gaps from `logs/working/test-audit.json` before pre-deploy QA.

This task should add focused tests only unless a tiny testability seam is unavoidable. Do not deploy, push, or contact live Telegram/Google/Yandex APIs.

## What to do

- Fix TA-001: add direct tests for `LiveTelegramBotClient.get_updates()`.
- Fix TA-002: add a test for startup readiness failure notification through the error bot.
- Leave TA-003 as non-blocking workflow hardening unless already covered by existing static tests.

## Acceptance Criteria

- [x] `get_updates()` request body includes offset, timeout, and limit.
- [x] `get_updates()` returns Telegram update dicts and rejects malformed result.
- [x] Malformed `get_updates()` errors do not expose bot tokens.
- [x] `run_bot()` readiness failure sends a sanitized startup failure event through the error bot when token is configured.
- [x] Startup failure notification test proves raw schema/secret text is not sent.
- [x] No external Telegram/Google/Yandex calls are made.

## Context Files

- [test-audit.json](../logs/working/test-audit.json)
- [app/bot/clients.py](/root/telegram_goals_bot/app/bot/clients.py)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [tests/test_boundaries.py](/root/telegram_goals_bot/tests/test_boundaries.py)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_boundaries.py tests/test_runtime_entrypoint.py -v` -> all pass

### Smoke
- `python -m pytest -q` -> all pass

## Post-completion

- [x] Write a brief report in `decisions.md` per the template.
- [x] If any audit finding is intentionally not fixed, describe the reason.
