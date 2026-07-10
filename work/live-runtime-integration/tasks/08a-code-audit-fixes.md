---
status: done
depends_on: [8]
wave: 5
skills: [code-writing]
verify: [smoke]
reviewers: []
teammate_name:
---

# Task 8a: Code audit fixes

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Fix the blocking findings from `logs/working/code-audit.json` before continuing to security/test audits and pre-deploy QA.

This task must preserve business-service ownership. Fix the live runtime layer and Telegram outbound boundary so the existing service responses become usable in live Telegram, and so runtime failures are handled safely.

## What to do

- Fix CA-001: send Telegram reply markup/callback data for `FlowResponse.buttons` and `FlowResponse.menu_items`.
- Fix CA-002: add polling error boundaries for `getUpdates` and per-update dispatch failures with sanitized admin errors and handled offset advancement.
- Fix CA-003: normalize readiness/check-config errors so Google schema/readiness failures exit clearly with code `2` and no traceback.
- Add focused tests for each fix.
- Do not start deploy workflows or contact live Telegram/Google/Yandex APIs.

## Acceptance Criteria

- [x] Consent/menu/weekly/insight responses can be sent with Telegram inline keyboard markup.
- [x] Stable callback constants are used for generated outbound callback data.
- [x] Polling loop reports sanitized update failures to the error bot and continues to later updates.
- [x] Polling loop does not advance offset when `getUpdates` itself fails.
- [x] `check-config` returns exit code `2` with a concise readiness/schema error when Google schema validation fails.
- [x] No raw update payload, tokens, credentials, or personal report text are included in runtime admin error messages.

## Context Files

- [code-audit.json](../logs/working/code-audit.json)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/bot/clients.py](/root/telegram_goals_bot/app/bot/clients.py)
- [app/bot/dispatch.py](/root/telegram_goals_bot/app/bot/dispatch.py)
- [app/bot/menus.py](/root/telegram_goals_bot/app/bot/menus.py)
- [app/services/participant_models.py](/root/telegram_goals_bot/app/services/participant_models.py)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)
- [tests/test_boundaries.py](/root/telegram_goals_bot/tests/test_boundaries.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_boundaries.py tests/test_runtime_entrypoint.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_boundaries.py tests/test_runtime_entrypoint.py -v` -> all pass

## Post-completion

- [x] Write a brief report in `decisions.md` per the template.
- [x] If any audit finding is intentionally not fixed, describe the reason.
