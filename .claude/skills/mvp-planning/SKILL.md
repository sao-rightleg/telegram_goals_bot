---
name: mvp-planning
description: Use when planning MVP scope, milestones, implementation sequence, approval gates, or release readiness for the Telegram goal tracker without adding out-of-scope infrastructure or features.
---

# MVP Planning

Use this skill to plan the "Трекер целей" MVP.

## Required context

Read:
- `AGENTS.md`
- `docs/00_project_overview.md`
- `docs/01_requirements.md`
- `docs/02_open_questions.md`
- `.codex/agents/product-owner.md`
- `.codex/agents/system-architect.md`

## MVP scope

Include:
- Telegram bot
- consent and Telegram ID identification
- participant goal, planned steps, progress, and insights
- weekly report flow
- voice messages up to 10 minutes with transcription
- captain manual reports for own team
- reminders and deadline closing
- silent participant notifications
- short Telegram team reports
- PDF team reports
- admin error notifications
- Google Sheets business storage
- SQLite technical state
- local audio and PDF storage

Out of MVP:
- web form
- PostgreSQL
- Docker
- Redis
- Celery
- web admin panel
- participant-created steps
- editing past weeks
- late status
- public group comparison
- advanced analytics
- coaching recommendations

## Approval gates

Before application code:
1. requirements approved
2. architecture approved
3. Google Sheets schema approved
4. SQLite state schema approved
5. Telegram scenarios approved
6. report formats approved
7. deployment plan approved
8. open blocking questions resolved

## Planning principles

- Build the shortest path to reliable weekly reporting.
- Keep business logic explicit.
- Separate MVP from later improvements.
- Do not guess open decisions silently.
- Prefer simple operations on one VPS.
- Preserve future extensibility without implementing future infrastructure now.

## Output

Return milestones, dependencies, risks, approval gates, and open questions.

Do not write application code unless the user explicitly asks after approvals.
