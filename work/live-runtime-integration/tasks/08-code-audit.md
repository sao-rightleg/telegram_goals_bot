---
status: planned
depends_on: [7]
wave: 5
skills: [code-reviewing]
verify: []
reviewers: []
teammate_name:
---

# Task 8: Code Audit

## Required Skills

Before executing the task, load:
- `/skill:code-reviewing` - [SKILL.md](/root/.codex/skills/code-reviewing/SKILL.md)

## Description

Review the feature implementation holistically after Tasks 1-7. Focus on architecture consistency, boundary use, runtime lifecycle, duplicated initialization, and whether new live layers preserve existing business-service ownership.

This is an analysis task. Do not change application code unless a separate fix task is created.

## What to do

- Read all files changed by Tasks 1-7 and the approved specs.
- Review runtime composition, Telegram client/downloader, dispatcher, Google Sheets adapter, Yandex transcriber, and test deploy artifacts as one system.
- Identify blocking code-quality or architecture findings with file/line references.
- Write a JSON audit report to the working log path.
- If no issues are found, write explicit OK with residual risks.

## Acceptance Criteria

- [ ] Audit covers all feature code and deploy artifacts.
- [ ] Findings are ordered by severity and include concrete file/line references.
- [ ] Report distinguishes blocking issues from minor recommendations.
- [ ] Report is saved at the expected path.
- [ ] No application code is changed directly by this audit task.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/config.py](/root/telegram_goals_bot/app/config.py)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/bot/clients.py](/root/telegram_goals_bot/app/bot/clients.py)
- [app/sheets/gateway.py](/root/telegram_goals_bot/app/sheets/gateway.py)
- [app/speech/transcription.py](/root/telegram_goals_bot/app/speech/transcription.py)
- [.github/workflows/deploy-test.yml](/root/telegram_goals_bot/.github/workflows/deploy-test.yml)
- [deploy/systemd/telegram-goals-bot-test.service](/root/telegram_goals_bot/deploy/systemd/telegram-goals-bot-test.service)

## Verification Steps

### Automated
- Confirm `work/live-runtime-integration/logs/working/code-audit.json` exists and is valid JSON.

## Details

**Files:**
- `work/live-runtime-integration/logs/working/code-audit.json` - write audit report.

**Dependencies:** Task 7.

**Edge cases:**
- Runtime creates multiple Google/Yandex clients unnecessarily.
- Dispatcher duplicates business rules already owned by services.
- Test deploy artifacts drift from runtime assumptions.
- Error handling masks operational failures too aggressively.

**Implementation hints:**
- Use code-review stance: findings first, concise summary second.
- Treat missing tests as findings only when they create concrete regression risk.

## Reviewers

None.

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you found blocking issues, request/follow a fix task before final QA.
