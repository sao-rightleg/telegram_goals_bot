---
status: planned
depends_on: [7]
wave: 5
skills: [test-master]
verify: []
reviewers: []
teammate_name:
---

# Task 10: Test Audit

## Required Skills

Before executing the task, load:
- `/skill:test-master` - [SKILL.md](/root/.codex/skills/test-master/SKILL.md)

## Description

Review feature tests for quality and adequacy before final QA. The audit should determine whether tests meaningfully cover the live runtime risks without requiring real Telegram, Google, or Yandex secrets.

This is an analysis task. Do not change application code or tests unless a separate fix task is created.

## What to do

- Read all tests created or modified by Tasks 1-7 and the approved specs.
- Check coverage of config validation, Telegram clients/downloader, dispatcher routing, Google schema validation, Yandex polling/failure, runtime composition, and test deploy isolation.
- Verify tests assert behavior and security properties rather than implementation trivia.
- Identify missing negative-path tests for L-feature risks.
- Write a JSON test audit report to the working log path.

## Acceptance Criteria

- [ ] Audit covers unit, integration, smoke, and deferred live E2E verification strategy.
- [ ] Findings include concrete missing/weak tests with file references.
- [ ] Report distinguishes blocking test gaps from acceptable deferred live smoke.
- [ ] Report is saved at the expected path.
- [ ] No tests or application code are changed directly by this audit task.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [tests/test_runtime_entrypoint.py](/root/telegram_goals_bot/tests/test_runtime_entrypoint.py)
- [tests/test_boundaries.py](/root/telegram_goals_bot/tests/test_boundaries.py)
- [tests/test_voice_processing_service.py](/root/telegram_goals_bot/tests/test_voice_processing_service.py)
- [tests/test_project_tooling.py](/root/telegram_goals_bot/tests/test_project_tooling.py)
- [tests/test_participant_sheets_gateway.py](/root/telegram_goals_bot/tests/test_participant_sheets_gateway.py)
- [tests/test_weekly_report_sheets_gateway.py](/root/telegram_goals_bot/tests/test_weekly_report_sheets_gateway.py)
- [tests/test_insight_sheets_gateway.py](/root/telegram_goals_bot/tests/test_insight_sheets_gateway.py)
- [tests/test_reports_sheets_gateway.py](/root/telegram_goals_bot/tests/test_reports_sheets_gateway.py)

## Verification Steps

### Automated
- Confirm `work/live-runtime-integration/logs/working/test-audit.json` exists and is valid JSON.

## Details

**Files:**
- `work/live-runtime-integration/logs/working/test-audit.json` - write audit report.

**Dependencies:** Task 7.

**Edge cases:**
- Tests pass only because live classes are not exercised.
- Tests require real credentials and cannot run in CI.
- Tests assert secrets directly or include fake values that look like real secrets.
- Dispatcher tests miss malformed callback or stale-state recovery.
- Deploy tests do not catch production/test mixing.

**Implementation hints:**
- Compare tests against user-spec acceptance criteria and tech-spec risks.
- Treat manual live smoke as valid only for real Telegram/Google/Yandex checks that cannot safely be automated in CI.

## Reviewers

None.

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you found blocking issues, request/follow a fix task before final QA.
