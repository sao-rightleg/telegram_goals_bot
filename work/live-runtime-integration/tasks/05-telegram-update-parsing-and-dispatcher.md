---
status: done
depends_on: [1, 2, 3, 4]
wave: 2
skills: [code-writing]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, test-reviewer]
teammate_name:
---

# Task 5: Telegram update parsing and dispatcher

## Required Skills

Before executing the task, load:
- `/skill:code-writing` - [SKILL.md](/root/.codex/skills/code-writing/SKILL.md)

## Description

Add runtime-level Telegram update parsing and dispatch updates into existing services. The dispatcher must keep handlers thin: parse Telegram input, build `TelegramUserContext`, call business services, and rely on those services for rules.

This task owns dispatcher/update parsing modules. Runtime CLI composition and polling lifecycle wiring are owned by Task 6.

## What to do

- Add internal DTOs for Telegram messages, callbacks, and updates.
- Parse Telegram update payloads for `/start`, plain text, callback data, and voice metadata.
- Define stable callback data constants/parsing for consent, menu, weekly report, insight, and captain flows.
- Route parsed updates into existing participant, weekly report, insight, voice, and captain services.
- Add safe malformed callback/update handling with sanitized admin error notification.
- Add tests with fake services/fake sheets/fake bots and temporary SQLite where useful.
- Keep business rules in services; do not duplicate role, deadline, duplicate-report, or consent logic in dispatcher.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write code -> confirm they pass.

- `tests/test_runtime_entrypoint.py::test_dispatcher_routes_start_to_participant_flow` - `/start` reaches participant flow.
- `tests/test_runtime_entrypoint.py::test_dispatcher_routes_weekly_text_to_active_report` - text in weekly report state reaches weekly report service.
- `tests/test_runtime_entrypoint.py::test_dispatcher_routes_insight_text_to_active_insight` - text in insight state reaches insight service.
- `tests/test_runtime_entrypoint.py::test_dispatcher_routes_voice_to_active_draft_service` - voice metadata reaches voice-enabled service.
- `tests/test_runtime_entrypoint.py::test_dispatcher_sanitizes_malformed_callback_error` - bad callback notifies admin without secrets/personal text.

## Acceptance Criteria

- [ ] Telegram update DTOs cover message, callback, text, command, and voice fields needed for smoke.
- [ ] `/start` routes to `ParticipantFlowService.handle_start()`.
- [ ] Consent and menu callbacks route to existing participant/captain/insight/weekly services.
- [ ] Weekly report status, step, text, voice, and done actions route to existing weekly report service.
- [ ] Insight add/list/full/text/voice/done actions route to existing insight service.
- [ ] Captain own-team/manual-report callbacks route to existing captain service.
- [ ] Malformed callbacks and invalid state produce safe response/admin error without leaking secrets.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/bot/menus.py](/root/telegram_goals_bot/app/bot/menus.py)
- [app/bot/messages.py](/root/telegram_goals_bot/app/bot/messages.py)
- [app/services/participant_flows.py](/root/telegram_goals_bot/app/services/participant_flows.py)
- [app/services/weekly_reports.py](/root/telegram_goals_bot/app/services/weekly_reports.py)
- [app/services/insights.py](/root/telegram_goals_bot/app/services/insights.py)
- [app/services/captains.py](/root/telegram_goals_bot/app/services/captains.py)
- [app/services/voice_messages.py](/root/telegram_goals_bot/app/services/voice_messages.py)
- [app/storage/dialog_state.py](/root/telegram_goals_bot/app/storage/dialog_state.py)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_participant_start_flow.py tests/test_weekly_report_start_flow.py tests/test_insight_add_flow.py tests/test_captain_team_flow.py tests/test_captain_manual_report_flow.py tests/test_runtime_entrypoint.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_participant_start_flow.py tests/test_weekly_report_start_flow.py tests/test_insight_add_flow.py tests/test_captain_team_flow.py tests/test_captain_manual_report_flow.py -v` -> all pass

## Details

**Files:**
- `app/bot/menus.py` - add callback constants/helpers if needed.
- `app/runtime.py` or a new runtime/bot dispatch module - add DTOs, parsing, and dispatcher.
- `tests/test_runtime_entrypoint.py` - add dispatcher routing and malformed callback tests.

**Dependencies:** Tasks 1-4.

**Edge cases:**
- Callback data has unknown prefix or malformed IDs.
- Text arrives with no active draft.
- Voice arrives with no active draft.
- Telegram update lacks username/chat optional fields.
- Service raises due to stale/invalid draft state.

**Implementation hints:**
- Prefer a small `dispatch_update()` surface that Task 6 can call from polling.
- Use existing `DialogStateRepository` to decide whether plain text belongs to weekly report or insight draft.
- Keep callback payloads short and stable.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-5/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-5/security-auditor-1.json`
- **test-reviewer** -> `work/live-runtime-integration/logs/working/task-5/test-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
