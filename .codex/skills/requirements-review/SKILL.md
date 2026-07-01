---
name: requirements-review
description: Use when reviewing or updating requirements for the Telegram goal tracker MVP, checking scope, contradictions, open questions, roles, deadlines, reports, storage decisions, and business logic before implementation.
---

# Requirements Review

Use this skill to review requirements, docs, PRDs, agent instructions, or implementation plans for "Трекер целей".

## Required context

Read before acting:
- `AGENTS.md`
- `docs/00_project_overview.md`
- `docs/01_requirements.md`
- `docs/02_open_questions.md`

If reviewing agent or skill files, also read the relevant files under `.codex/agents/` or `.codex/skills/`.

## MVP boundaries

Protect these decisions:
- Telegram is the MVP channel.
- Google Sheets is the MVP business database.
- SQLite stores only technical bot state and drafts.
- Audio and PDF files are stored locally on VPS.
- Participants cannot add new planned steps in MVP.
- Participants cannot edit previous weeks.
- Late reports after Sunday 23:59 Yekaterinburg time do not change weekly status.
- Insights are separate from progress.

Do not add PostgreSQL, Docker, Redis, Celery, web admin panel, advanced analytics, public leaderboard, payments, mobile app, or coaching recommendations to MVP unless explicitly requested.

## Review checklist

Check for:
- contradictions with `AGENTS.md` or requirements
- missing role permissions
- hidden business-logic changes
- unclear deadline behavior
- incorrect storage boundary between Google Sheets and SQLite
- report visibility mistakes
- privacy or consent gaps
- unsupported status values such as yellow late status
- ambiguous open decisions that should be added to `docs/02_open_questions.md`

## Output

Return:
1. Blockers
2. Non-blocking issues
3. Suggested wording or doc changes
4. Open questions requiring user decision

Do not write application code.
