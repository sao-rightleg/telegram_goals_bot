---
name: qa-edge-cases
description: Use when creating QA scenarios or reviewing edge cases for the Telegram goal tracker MVP, especially deadlines, roles, captain reports, voice processing, Google Sheets consistency, SQLite state, reports, and privacy.
---

# QA Edge Cases

Use this skill to find what can break before implementation or release.

## Required context

Read:
- `AGENTS.md`
- `docs/01_requirements.md`
- `docs/02_open_questions.md`
- `.codex/agents/qa-engineer.md`

## Priority areas

Test hardest:
- deadline and timezone behavior
- weekly status scoring
- role permissions
- captain manual reports
- Google Sheets consistency
- SQLite draft recovery
- voice transcription failures
- report generation and sending
- privacy and recipient routing
- duplicate scheduler execution

## Must-protect rules

- Final weekly statuses are only 🟩 🟦 🟥 ⬛; ⬜ is reserved for current/future weeks before deadline.
- No yellow late status.
- Late reports do not change weekly status.
- Insights do not change progress.
- Dropped participants remain visible but are excluded from victory percentage.
- Captains see only own team.
- Trackers see only assigned teams.
- Group comparison goes only to admin and Sitnikov.

## Output format

For each issue or scenario, provide:
1. What can break
2. Why it matters
3. How to test it
4. Expected behavior
5. Required fix or decision

Separate blockers from non-blocking risks.

Do not write production code.
