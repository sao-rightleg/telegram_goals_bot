# MVP Deployment Preparation

## Purpose

This document is the pre-production checklist for the Telegram Goals Bot MVP.

Production deployment must be executed only through GitHub CI/CD after explicit user approval. Direct SSH/server actions are reserved for emergency debugging of broken production.

## Current Status

- CI workflow: `.github/workflows/ci.yml`
- Manual test-live deploy workflow: `.github/workflows/deploy-test.yml`
- Manual production deploy workflow: `.github/workflows/deploy-production.yml`
- Production target: custom VPS, `systemd` service
- Readiness CLI: `telegram-goals-bot check-config` / `telegram-goals-bot init-storage`
- Runtime command: `telegram-goals-bot run`
- Committed systemd unit template: `deploy/systemd/telegram-goals-bot.service`
- Committed test systemd unit template: `deploy/systemd/telegram-goals-bot-test.service`
- Live polling runtime: implemented; production remains blocked until test-live smoke and explicit production approval

First production launch is blocked until test-live deployment and smoke verification pass, and the user explicitly approves a separate production deployment.

## GitHub Setup Checklist

- Create GitHub environment: `production`
- Require manual approval for the `production` environment
- Create GitHub environment: `test`
- Add production deployment secrets:
  - `VPS_HOST`
  - `VPS_PORT`
  - `VPS_USER`
  - `VPS_SSH_KEY`
  - `VPS_APP_DIR`
  - `VPS_SERVICE_NAME`
- Add test-live deployment secrets:
  - `TEST_VPS_HOST`
  - `TEST_VPS_PORT`
  - `TEST_VPS_USER`
  - `TEST_VPS_SSH_KEY`
  - `TEST_VPS_APP_DIR=/opt/telegram_goals_bot_test`
  - `TEST_VPS_SERVICE_NAME=telegram-goals-bot-test.service`
- Confirm branch protection for `main`
- Confirm CI is required for pull requests to `main`

Do not store Telegram, Google, transcription, or SSH secret values in repository files.

## Application Configuration Checklist

Store local values in `.env`. Store production values in protected server files and/or GitHub Actions secrets according to the final systemd unit design.

Required application configuration:

- `MAIN_TELEGRAM_BOT_TOKEN`
- `ERROR_TELEGRAM_BOT_TOKEN`
- `NOTIFICATION_TELEGRAM_BOT_TOKEN`
- `GOOGLE_SHEETS_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `ADMIN_TELEGRAM_ID`
- `ADMIN_ERROR_CHAT_ID`
- `SITNIKOV_TELEGRAM_ID`
- `IVAN_LARKIN_TELEGRAM_ID`
- `MARIA_TELEGRAM_ID`
- `TRANSCRIPTION_PROVIDER`
- `TRANSCRIPTION_API_KEY`
- `APP_TIMEZONE=Asia/Yekaterinburg`
- `SQLITE_DB_PATH`
- `AUDIO_STORAGE_DIR`
- `PDF_STORAGE_DIR`
- `LOG_LEVEL`

## VPS Folder Checklist

Recommended base:

```text
/opt/telegram_goals_bot/
├── current -> releases/{sha}
├── releases/
└── shared/
    ├── data/audio/
    ├── data/sqlite/
    ├── reports/pdf/
    ├── logs/
    └── backups/
        ├── sqlite/
        ├── google_sheets_exports/
        └── pdf/
```

Generated data must remain outside git-tracked release files.

Test-live base:

```text
/opt/telegram_goals_bot_test/
├── current -> releases/{sha}
├── releases/
└── shared/
    ├── .env
    ├── data/audio/
    ├── data/sqlite/
    ├── reports/pdf/
    ├── logs/
    └── backups/
        ├── sqlite/
        ├── google_sheets_exports/
        └── pdf/
```

The test-live directory, service, bots, Google Sheet, and credentials must be separate from production.

## systemd Checklist

Before first production deploy:

- Review and install `deploy/systemd/telegram-goals-bot.service`.
- Configure service environment loading from a protected file.
- Use `WorkingDirectory=/opt/telegram_goals_bot/current`.
- Use the release-local virtual environment.
- Ensure service user can read config and write SQLite/audio/PDF/log paths.
- The same service process runs Telegram polling and scheduled reminders; no separate scheduler timer is installed.
- Ensure GitHub deploy user can restart the service through a narrow sudo rule.
- Run `telegram-goals-bot --env-file /opt/telegram_goals_bot/shared/.env check-config`.

Manual inspection commands:

```bash
systemctl status telegram-goals-bot
journalctl -u telegram-goals-bot -f
```

Before first test-live deploy:

- Install `deploy/systemd/telegram-goals-bot-test.service`.
- Configure protected test env file at `/opt/telegram_goals_bot_test/shared/.env`.
- Use separate test Telegram bot tokens, test Google Sheet, and test Yandex credentials.
- The same test service process runs Telegram polling and scheduled reminders.
- Ensure GitHub deploy user can restart only `telegram-goals-bot-test.service` through a narrow sudo rule.
- Run `telegram-goals-bot --env-file /opt/telegram_goals_bot_test/shared/.env check-config`.

Manual test inspection commands:

```bash
systemctl status telegram-goals-bot-test.service
journalctl -u telegram-goals-bot-test.service -f
```

## Backup and Retention Checklist

- SQLite backup: daily, 14-day retention.
- Google Sheets export: periodic `.xlsx` or `.csv`, 14-day retention.
- Audio files: delete one month after recording.
- PDF files: keep locally for six months after challenge end.
- Backup location: `/opt/telegram_goals_bot/shared/backups/` or the project-approved VPS backup path.

## Pre-Production Smoke Test

Use a separate test Telegram bot and test Google Sheet.

- Known participant can start the bot and pass consent.
- Unknown Telegram user receives the approved rejection text.
- Unknown-user event reaches admin error chat through the error bot.
- Participant can view goal, planned steps, and progress.
- Participant can submit weekly report text.
- Green/blue weekly report requires planned step selection.
- Insight saves separately from weekly progress.
- Voice under 10 minutes is saved and transcribed.
- Voice over 10 minutes is rejected.
- Captain can view only own team.
- Captain can submit manual report for own-team participant before deadline.
- Scheduler reminder skips participants who already reported.
- Week close creates gray reports idempotently.
- Silent participant notification is scoped to captain/tracker teams.
- Team Telegram summary is routed to correct recipients.
- Team PDF is generated and sent to allowed recipients.
- Admin/Sitnikov receive full summaries.
- Captains/trackers do not receive group comparison.

## Deploy Procedure

### Test-Live

1. Confirm explicit user approval to run the test deploy workflow.
2. Confirm GitHub `test` environment exists.
3. Confirm all `TEST_*` GitHub deployment secrets exist and point only to test resources.
4. Confirm `/opt/telegram_goals_bot_test/shared/.env` contains test-only application config.
5. Run `Deploy Test` manually in GitHub Actions.
6. Verify GitHub runner tests pass.
7. Verify VPS release tests pass.
8. Verify `check-config` passes before symlink switch.
9. Verify `systemctl status telegram-goals-bot-test.service`.
10. Run the approved test-live Telegram smoke checklist.

Passing test-live does not approve production.

### Production

1. Confirm explicit user approval for production deploy and target ref.
2. Confirm GitHub `production` environment approval is enabled.
3. Confirm all GitHub deployment secrets exist.
4. Confirm live runtime, systemd unit, and protected env file are ready.
5. Run `Deploy Production` manually in GitHub Actions.
6. Verify GitHub runner tests pass.
7. Verify VPS release tests pass.
8. Verify `systemctl status telegram-goals-bot`.
9. Run smoke test with test bot and test sheets before switching to production bot data.

## Rollback Procedure

1. Identify the previous release directory under `VPS_APP_DIR/releases/`.
2. Point `VPS_APP_DIR/current` back to the previous release.
3. Restart `VPS_SERVICE_NAME` through GitHub Actions or emergency SSH.
4. Verify service status and logs.
5. Record rollback reason and failed SHA.
