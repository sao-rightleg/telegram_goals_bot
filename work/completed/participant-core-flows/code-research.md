# Code Research: participant-core-flows

## Current foundation

The repository already has the `mvp-foundation` implementation:

- Python package metadata and pytest setup in `pyproject.toml`.
- Settings and redaction in `app/config.py` and `app/logging.py`.
- SQLite technical-state schema initialization in `app/storage/sqlite.py`.
- Storage path policy in `app/storage/paths.py`.
- Scheduler constants in `app/scheduler/calendar.py`.
- External integration boundaries/fakes in:
  - `app/bot/clients.py`
  - `app/sheets/gateway.py`
  - `app/services/notifications.py`
  - `app/reports/generator.py`
  - `app/speech/transcription.py`
- Foundation tests in `tests/`.

Full suite currently passes: 35 tests.

## Relevant existing boundaries

- `FakeBotClient` can record outgoing messages, but there is no incoming Telegram update handler yet.
- `FakeSheetsGateway` currently supports weekly reports and insights only. Participant, consent, goal, planned-step, and progress read/write methods do not exist yet.
- `NotificationRouter` can route technical errors only to the error bot.
- SQLite has `dialog_states` and draft tables, but no repository methods yet.

## Gaps for this feature

- No `/start` handler or command router.
- No participant identity service.
- No Google Sheets participant/goal/step/progress read boundary.
- No consent write boundary.
- No role-aware menu builder.
- No user-facing message templates for start/consent/menu/views in code.
- No technical-state repository for active consent/menu flows.
- No unknown-user error event/routing orchestration.

## Suggested implementation direction for tech-spec

- Keep Telegram handlers thin and adapter-agnostic where possible.
- Add service-level orchestration that can be tested without live Telegram or Google credentials.
- Extend Sheets boundary/fake with reads for participants, goals, planned steps, weekly report/progress history, and consent update.
- Use existing `NotificationRouter` for unknown-user admin error routing.
- Use SQLite only for dialog/current-flow technical state, not for participant/goals/steps business facts.
- Keep live Telegram SDK and live Google API adapter decisions in tech-spec, not user-spec.
