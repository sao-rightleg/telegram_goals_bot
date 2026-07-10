---
status: planned
depends_on: [7]
wave: 5
skills: [security-auditor]
verify: []
reviewers: []
teammate_name:
---

# Task 9: Security Audit

## Required Skills

Before executing the task, load:
- `/skill:security-auditor` - [SKILL.md](/root/.codex/skills/security-auditor/SKILL.md)

## Description

Review the feature implementation for security, privacy, and environment isolation risks. The audit must focus on secret handling, token redaction, credential paths, Google Sheets access, Yandex credentials, Telegram role boundaries, personal data leakage, and CI/CD separation between test and production.

This is an analysis task. Do not change application code unless a separate fix task is created.

## What to do

- Read all security-relevant files changed by Tasks 1-7 and the approved specs.
- Review configuration, logging/redaction, Telegram adapter errors, Google/Yandex auth handling, dispatcher error paths, and deploy workflow secrets.
- Verify production deploy remains blocked and test deploy cannot restart production by default.
- Write a JSON security audit report to the working log path.
- If no issues are found, write explicit OK with residual risks.

## Acceptance Criteria

- [ ] Audit covers secret handling, external API auth, Telegram authorization boundaries, personal data exposure, and CI/CD isolation.
- [ ] Findings include severity, file/line references, impact, and recommended fix.
- [ ] Report confirms whether bot tokens, API keys, Google credentials, personal report text, audio contents, and PDF contents are protected.
- [ ] Report is saved at the expected path.
- [ ] No application code is changed directly by this audit task.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [app/config.py](/root/telegram_goals_bot/app/config.py)
- [app/logging.py](/root/telegram_goals_bot/app/logging.py)
- [app/runtime.py](/root/telegram_goals_bot/app/runtime.py)
- [app/bot/clients.py](/root/telegram_goals_bot/app/bot/clients.py)
- [app/sheets/gateway.py](/root/telegram_goals_bot/app/sheets/gateway.py)
- [app/speech/transcription.py](/root/telegram_goals_bot/app/speech/transcription.py)
- [.github/workflows/deploy-test.yml](/root/telegram_goals_bot/.github/workflows/deploy-test.yml)
- [deploy/systemd/telegram-goals-bot-test.service](/root/telegram_goals_bot/deploy/systemd/telegram-goals-bot-test.service)

## Verification Steps

### Automated
- Confirm `work/live-runtime-integration/logs/working/security-audit.json` exists and is valid JSON.

## Details

**Files:**
- `work/live-runtime-integration/logs/working/security-audit.json` - write audit report.

**Dependencies:** Task 7.

**Edge cases:**
- HTTP exceptions include full URLs with bot tokens.
- Admin errors include personal report text or transcription text.
- Google credential file contents are accidentally logged.
- Test workflow uses production environment or service names.
- Dispatcher allows forged participant/captain callback data to bypass service checks.

**Implementation hints:**
- Verify both code behavior and test assertions for non-leakage.
- Treat missing negative tests around secrets or role boundaries as concrete findings when risk is material.

## Reviewers

None.

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you found blocking issues, request/follow a fix task before final QA.
