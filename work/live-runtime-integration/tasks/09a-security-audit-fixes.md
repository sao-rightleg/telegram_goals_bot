---
status: done
depends_on: [9]
wave: 5
skills: [code-writing, deploy-pipeline]
verify: [smoke]
reviewers: []
teammate_name:
---

# Task 9a: Security audit fixes

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)
- `/skill:deploy-pipeline` - [SKILL.md](/root/.codex/skills/deploy-pipeline/SKILL.md)

## Description

Fix the blocking findings from `logs/working/security-audit.json` before continuing to test audit and pre-deploy QA.

This task is limited to dependency/tooling and runtime/deploy hardening. Do not deploy, push, contact external APIs, or change business logic.

## What to do

- Fix SA-001: update dev pytest dependency so CI/test deploy resolves to a non-vulnerable version.
- Fix SA-002: enforce private permissions for runtime SQLite/audio/PDF storage directories and files, including test-live deploy/systemd defaults.
- Add focused tests for the new constraints.
- Leave SA-003 as a non-blocking production-hardening item unless it can be safely addressed without requiring new secrets.

## Acceptance Criteria

- [x] Dev pytest dependency allows/requires a version fixed for PYSEC-2026-1845.
- [x] `initialize_runtime()` creates/chmods SQLite, audio, and PDF storage directories to private permissions.
- [x] SQLite database file is restricted after initialization.
- [x] Test-live deploy creates sensitive shared directories with private permissions.
- [x] Test systemd unit applies a restrictive umask.
- [x] No deployment, push, or external API action is performed.

## Context Files

- [security-audit.json](../logs/working/security-audit.json)
- [pyproject.toml](/root/telegram_goals_bot/pyproject.toml)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [.github/workflows/deploy-test.yml](/root/telegram_goals_bot/.github/workflows/deploy-test.yml)
- [deploy/systemd/telegram-goals-bot-test.service](/root/telegram_goals_bot/deploy/systemd/telegram-goals-bot-test.service)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)
- [tests/test_project_tooling.py](/root/telegram_goals_bot/tests/test_project_tooling.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_runtime_entrypoint.py tests/test_project_tooling.py -v` -> all pass
- `uv tool run pip-audit -r <generated requirements from pyproject>` -> no known vulnerabilities

### Smoke
- `python -m pytest -q` -> all pass

## Post-completion

- [x] Write a brief report in `decisions.md` per the template.
- [x] If any audit finding is intentionally not fixed, describe the reason.
