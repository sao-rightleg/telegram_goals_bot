# MVP Deployment Preparation

## Purpose

This document is the pre-production checklist for the Telegram Goals Bot MVP.

Production deployment must be executed only through GitHub CI/CD after explicit user approval. Direct SSH/server actions are reserved for emergency debugging of broken production.

## Current Status

- CI workflow: `.github/workflows/ci.yml`
- Manual production deploy workflow: `.github/workflows/deploy-production.yml`
- Production target: custom VPS, `systemd` service
- Readiness CLI: `telegram-goals-bot check-config` / `telegram-goals-bot init-storage`
- Runtime command: `telegram-goals-bot run`
- Committed systemd unit template: `deploy/systemd/telegram-goals-bot.service`
- Live polling runtime: not yet implemented in the repository

First production launch is blocked until live Telegram/Google/transcription adapters and the polling runtime are implemented. The current `run` command fails explicitly until that task is complete.

## GitHub Setup Checklist

- Create GitHub environment: `production`
- Require manual approval for the `production` environment
- Add deployment secrets:
  - `VPS_HOST`
  - `VPS_PORT`
  - `VPS_USER`
  - `VPS_SSH_KEY`
  - `VPS_APP_DIR`
  - `VPS_SERVICE_NAME`
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

## systemd Checklist

Before first production deploy:

- Implement live Telegram polling runtime behind `telegram-goals-bot run`.
- Review and install `deploy/systemd/telegram-goals-bot.service`.
- Configure service environment loading from a protected file.
- Use `WorkingDirectory=/opt/telegram_goals_bot/current`.
- Use the release-local virtual environment.
- Ensure service user can read config and write SQLite/audio/PDF/log paths.
- Ensure GitHub deploy user can restart the service through a narrow sudo rule.
- Run `telegram-goals-bot --env-file /opt/telegram_goals_bot/shared/.env check-config`.

Manual inspection commands:

```bash
systemctl status telegram-goals-bot
journalctl -u telegram-goals-bot -f
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
