---
status: done
depends_on: []
wave: 1
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 1: Runtime configuration and provider selection

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Extend typed runtime settings so the live runtime can distinguish valid test-live Yandex configuration from incomplete or unsafe configuration. This task prepares configuration only; it must not create live clients, start polling, or contact external services.

The result should keep existing strict three-bot token validation and add provider-specific transcription settings without exposing secret values in errors, logs, reprs, or test output.

## What to do

- Add typed settings for transcription provider selection and Yandex-specific runtime values.
- Add typed settings for Telegram polling/request timeout values.
- Keep current required environment variables working and preserve backwards-compatible defaults where safe.
- Validate `TRANSCRIPTION_PROVIDER=yandex` fail-fast when mandatory Yandex values are missing or invalid.
- Update `.env.example` with variable names only; do not add real values or example secrets.
- Add tests that prove missing Yandex config fails clearly and valid fake config loads.
- Keep redaction behavior covering all new token/key/credential fields.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_config.py::test_load_settings_accepts_yandex_transcription_config` - valid fake Yandex settings load into typed config.
- `tests/test_config.py::test_yandex_provider_requires_folder_and_credentials` - incomplete Yandex config raises `ConfigurationError`.
- `tests/test_config.py::test_redaction_covers_yandex_and_transcription_secrets` - new secret fields are redacted.
- `tests/test_runtime_entrypoint.py::test_runtime_env_includes_transcription_provider_config` - runtime test env can include provider config without breaking existing storage initialization.

## Acceptance Criteria

- [ ] `Settings` exposes transcription and Telegram runtime sections.
- [ ] `TRANSCRIPTION_PROVIDER=yandex` is accepted only with complete fake test config.
- [ ] Missing provider-specific settings produce `ConfigurationError` without secret values.
- [ ] `.env.example` contains all new config keys with empty/default values only.
- [ ] Existing config/runtime tests still pass.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/config.py](/root/telegram_goals_bot/app/config.py)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/speech/transcription.py](/root/telegram_goals_bot/app/speech/transcription.py)
- [.env.example](/root/telegram_goals_bot/.env.example)
- [tests/test_config.py](/root/telegram_goals_bot/tests/test_config.py)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_config.py tests/test_runtime_entrypoint.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_config.py tests/test_runtime_entrypoint.py -v` -> all pass

## Details

**Files:**
- `app/config.py` - add dataclasses, env parsing, validation, and redaction coverage.
- `.env.example` - add Yandex/Telegram runtime variable names only.
- `tests/test_config.py` - cover valid/invalid provider settings and redaction.
- `tests/test_runtime_entrypoint.py` - keep runtime fake env aligned with strict config.

**Dependencies:** None.

**Edge cases:**
- Empty strings must be treated as missing values.
- Numeric timeout/poll values must reject non-numeric or unsafe values.
- A future non-Yandex provider should fail clearly unless explicitly supported.
- New credential paths must not be checked into git and must not leak through errors.

**Implementation hints:**
- Preserve the current `load_settings(..., strict=True)` behavior for Telegram tokens.
- Reuse existing `_optional_value`, `_required_value`, and redaction conventions.
- Keep provider validation inside config loading so runtime composition receives typed, trusted values.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-1/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-1/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-1/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
