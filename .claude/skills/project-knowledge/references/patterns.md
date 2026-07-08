# Patterns

## Development Workflow

Before coding:

1. Read `CLAUDE.md` or generated `AGENTS.md`.
2. Load this `project-knowledge` skill.
3. Read relevant `docs/*.md`.
4. Check `docs/02_open_questions.md`.
5. Update requirements or architecture if needed.
6. Ask for approval when a requirement changes or an open decision blocks implementation.
7. Only then write code.

Do not silently change business logic.

## Methodology Workflow

For new feature work, use the Molyanov pipeline:

1. User Spec: `work/{feature}/user-spec.md`
2. Tech Spec: `work/{feature}/tech-spec.md`
3. Task decomposition: `work/{feature}/tasks/*.md`
4. Implementation via task or feature execution.
5. Done: update Project Knowledge and archive to `work/completed/{feature}/`.

For the current project, existing `docs/*.md` are the pre-existing planning base. Convert new work into `work/{feature}/` specs before application code.

## Code Organization Expectations

Keep Telegram bot logic separate from:

- Google Sheets integration.
- SQLite state storage.
- Voice transcription.
- Report generation.
- Scheduler.
- Notification routing.

Prefer simple MVP implementation over overengineering, but avoid choices that block future web form or PostgreSQL migration.

## Security Rules

- Never commit `.env`, secrets, API keys, Google credentials, or token files.
- Do not expose tokens in logs.
- Do not send personal data to unauthorized chats.
- Restrict Google Sheets access.
- Store only necessary data.
- Require participant consent before continuing.
- For voice processing failures after a local audio download, delete the just-downloaded audio file unless a future feature explicitly adds failed attachment retention/tracking.

## Error Handling

Admin must receive Telegram error notifications for:

- Unknown Telegram user.
- Participant not found.
- Google Sheets read/write error.
- SQLite error.
- Voice transcription error.
- PDF generation error.
- Report sending error.
- Scheduler error.
- Invalid dialog state.
- Missing required data.

For report delivery errors, keep admin messages technical and sanitized: include report type, scope, recipient role/id, and failure category; do not include raw personal report text, secrets, token-like strings, or PDF contents.

Error messages must contain enough context to fix the issue, but must not expose secrets or unnecessary personal data.

## Testing Focus

High-risk tests:

- Role access boundaries.
- Deadline behavior.
- Google Sheets read/write failures.
- SQLite state recovery.
- Voice duration and transcription failure.
- Report generation and recipient routing.
- Scheduler idempotency.
- Secret and personal-data leakage.

## Current Test Coverage Shape

The implemented MVP slices are covered with local pytest tests and fake external boundaries. Pre-deploy QA passed for foundation, participant core flows, weekly report flow, insight flow, voice processing, captain flows, scheduler deadlines, and reports flow without production secrets or live API calls.

Tests are organized around service boundaries and business risks: config validation, secret redaction, SQLite schema/repositories, participant and captain role/consent gates, weekly report deadline and duplicate guards, Sheets fake behavior, insight privacy boundaries, captain forged-selection and own-team boundaries, voice duration and failure retention behavior, scheduler reminder recipient filtering/retry/idempotency, week-close partial failure recovery, silent-notification team privacy, report aggregation/formatting/PDF generation, role-safe report recipient planning, report delivery idempotency, report failure isolation, generated artifact safety, and forbidden out-of-scope dependencies.

When adding the next feature, preserve the same fake-boundary approach until live integration tasks explicitly require real SDKs or external credentials.
