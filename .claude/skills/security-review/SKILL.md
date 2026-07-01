---
name: security-review
description: Use when reviewing security and privacy for the Telegram goal tracker MVP, including personal data, secrets, role-based access, Google Sheets permissions, SQLite files, audio, PDFs, logs, consent, and error notifications.
---

# Security Review

Use this skill for requirements, architecture, deployment, code review, and operational security.

## Required context

Read:
- `AGENTS.md`
- `docs/01_requirements.md`
- `.codex/agents/security-reviewer.md`

## Main risks

The system processes:
- real names
- Telegram IDs and usernames
- team membership
- goals and financial goal values
- weekly reports
- insights
- voice messages
- transcriptions
- PDF reports

## Hard rules

- Do not commit `.env`.
- Do not expose bot tokens or API keys.
- Do not commit Google credentials.
- Do not commit SQLite databases, audio files, PDFs, or logs.
- Do not send personal data to unnecessary chats.
- Enforce role permissions server-side.
- Require consent before collecting reports, insights, or voice messages.
- Store audio and PDFs in non-public local paths.
- Avoid secrets and excessive personal data in logs and admin error messages.

## Role boundaries

- Participant sees only own data.
- Captain sees own team only.
- Tracker sees assigned teams only.
- Admin sees all data and errors.
- Alexander Sitnikov sees all reports and group comparison, but not raw technical errors unless explicitly required.

## Review checklist

Check:
- `.gitignore` protects sensitive/generated files
- `.env.example` has placeholders only
- credentials are external to git
- Google Sheets is not publicly editable
- consent is stored
- recipient routing cannot leak PDFs
- audio and PDF paths are not public URLs
- logs hide secrets
- unknown users cannot access bot data
- errors are actionable but not overexposed

## Output

Report findings by severity: critical, high, medium, low.

For each finding include impact and mitigation.

Do not add heavyweight infrastructure to MVP unless explicitly requested.
