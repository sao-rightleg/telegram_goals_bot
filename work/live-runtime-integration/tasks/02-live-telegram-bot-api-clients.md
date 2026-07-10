---
status: done
depends_on: []
wave: 1
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 2: Live Telegram Bot API clients

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Implement concrete Telegram Bot API clients behind the existing `BotClient` and `TelegramFileDownloader` boundaries. The three-bot model must remain explicit: main, error, and notification clients are separate by token and purpose.

This task covers outbound Telegram API behavior and file download only. It must not implement polling or dispatcher routing.

## What to do

- Add a concrete Telegram bot client that implements `send_message()` and `send_document()`.
- Add a concrete Telegram file downloader that resolves Telegram file paths and writes bytes to the requested local destination.
- Keep `FakeBotClient` and `FakeTelegramFileDownloader` unchanged for local tests.
- Ensure HTTP errors are raised or mapped with sanitized context.
- Add tests using a fake HTTP transport/client; do not call the real Telegram API.
- Add dependency metadata needed for the HTTP client if not already present.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_boundaries.py::test_live_telegram_client_sends_message_request` - verifies Bot API method, payload, and returned `OutgoingMessage`.
- `tests/test_boundaries.py::test_live_telegram_client_sends_document_request` - verifies multipart/document send without leaking token.
- `tests/test_boundaries.py::test_live_telegram_file_downloader_writes_requested_path` - verifies `getFile` plus file download writes destination.
- `tests/test_boundaries.py::test_live_telegram_errors_are_sanitized` - failures do not expose bot token.

## Acceptance Criteria

- [ ] Concrete Telegram client implements `BotClient`.
- [ ] Concrete Telegram downloader implements `TelegramFileDownloader`.
- [ ] Main/error/notification clients can be constructed independently from token and purpose.
- [ ] Downloaded files are written only to the requested destination path.
- [ ] Tokens are not included in exception messages, logs, or test assertions.
- [ ] Existing fake boundary tests still pass.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/bot/clients.py](/root/telegram_goals_bot/app/bot/clients.py)
- [app/services/notifications.py](/root/telegram_goals_bot/app/services/notifications.py)
- [app/storage/paths.py](/root/telegram_goals_bot/app/storage/paths.py)
- [tests/test_boundaries.py](/root/telegram_goals_bot/tests/test_boundaries.py)
- [pyproject.toml](/root/telegram_goals_bot/pyproject.toml)

## Verification Steps

### Automated
- `python -m pytest tests/test_boundaries.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_boundaries.py -v` -> all pass

## Details

**Files:**
- `app/bot/clients.py` - add live Telegram client/downloader classes and sanitized errors.
- `tests/test_boundaries.py` - add HTTP-level fake tests for live classes.
- `pyproject.toml` - add the HTTP dependency if required by implementation.

**Dependencies:** None. If Task 1 has already added typed timeout/request settings, use them through runtime composition later; this client task should remain constructible with explicit arguments for tests.

**Edge cases:**
- Telegram API returns `ok=false`.
- HTTP request raises timeout or network error.
- Document path does not exist.
- Telegram file path resolution succeeds but download fails.

**Implementation hints:**
- Keep token out of stringified URL/error messages by storing sanitized request metadata separately.
- Keep live classes small and protocol-focused; polling belongs to later runtime tasks.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-2/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-2/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-2/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
