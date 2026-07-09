# Deployment

## Current State

Production deployment is approved as a `systemd` service on VPS for MVP.

Do not deploy or push to production without explicit user approval.

All deployments must go through GitHub CI/CD unless emergency debugging of broken production requires direct server access.

Docker, Redis, Celery, Kubernetes, and complex DevOps are out of MVP.

The repository currently contains locally verified MVP slices for the foundation, participant core flows, weekly report flow, insight flow, voice processing input for weekly-report/insight drafts, captain flows, scheduler deadlines, and reports flow. They have passed pre-deploy QA with fake/local boundaries; no production deployment or live Telegram/Google/transcription integration has been performed as part of those feature completions.

## GitHub CI/CD

CI is configured in `.github/workflows/ci.yml`.

- Trigger: pull requests to `main` and pushes to `main`.
- Skip logic: docs-only changes under Markdown/text, `.claude/`, `.codex/`, `docs/`, and `work/` skip the Python test job.
- Test job: Python 3.10, `pip install -e ".[dev]"`, then `pytest`.

Production deployment is configured in `.github/workflows/deploy-production.yml`.

- Trigger: manual `workflow_dispatch` only.
- Protection: GitHub `production` environment should require manual approval before the job receives production secrets.
- Pre-deploy gate: installs the package and runs `pytest` on GitHub runner before uploading anything.
- Target: custom VPS with existing `systemd` service.
- Deployment shape: uploads a source archive, creates a release directory under `VPS_APP_DIR/releases/{sha}`, installs a release-local `.venv`, runs tests on the VPS release, updates `VPS_APP_DIR/current`, then restarts `VPS_SERVICE_NAME`.
- Runtime limitation: the repository defines readiness CLI commands and a committed systemd unit template, but live Telegram polling runtime is not implemented yet. First production launch requires a separate live-runtime adapter task before the service can stay healthy.

Do not run the production workflow until production secrets, GitHub environment protection, live runtime, systemd unit installation, and smoke checklist are ready and explicitly approved.

Detailed deployment readiness checklist: `docs/09_deployment_preparation.md`.

The deploy user on the VPS needs a narrow passwordless sudo rule for restarting and checking only the configured bot service.

Runtime readiness commands:

- `telegram-goals-bot --env-file /opt/telegram_goals_bot/shared/.env check-config`
- `telegram-goals-bot --env-file /opt/telegram_goals_bot/shared/.env init-storage`
- `telegram-goals-bot --env-file /opt/telegram_goals_bot/shared/.env run`

The `run` command currently exits with a clear not-implemented error until live Telegram polling adapters are added.

## Environment Variables and Credentials

Use `.env` or protected credential files locally. Use GitHub Actions secrets in CI/CD.

Required configuration is expected to include:

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
- `APP_TIMEZONE`
- `SQLITE_DB_PATH`
- `AUDIO_STORAGE_DIR`
- `PDF_STORAGE_DIR`
- `LOG_LEVEL`

Never ask the user to paste secret values in chat.

Required GitHub Actions secrets for production deployment:

| Secret | Purpose | Workflow |
| --- | --- | --- |
| `VPS_HOST` | VPS host name or IP address. | `deploy-production.yml` |
| `VPS_PORT` | SSH port. Optional; defaults to `22` when empty. | `deploy-production.yml` |
| `VPS_USER` | SSH user used by GitHub Actions. | `deploy-production.yml` |
| `VPS_SSH_KEY` | Private SSH deploy key with access to the VPS user. | `deploy-production.yml` |
| `VPS_APP_DIR` | Base app directory on VPS, for example `/opt/telegram_goals_bot`. | `deploy-production.yml` |
| `VPS_SERVICE_NAME` | systemd service name, for example `telegram-goals-bot`. | `deploy-production.yml` |

Application secrets remain outside the repository. Store local values in `.env` or protected credential files. Store production values on the VPS and/or GitHub Actions secrets, depending on the final systemd unit design.

## Local Runtime Paths

Recommended local folders:

- `data/audio/`
- `data/sqlite/`
- `reports/pdf/`
- `logs/`
- `backups/sqlite/`
- `backups/google_sheets_exports/`
- `backups/pdf/`

Generated files, credentials, logs, SQLite databases, audio files, PDFs, and backups must not be committed.

## Operations

Manual service commands:

- `systemctl status telegram-goals-bot`
- `systemctl restart telegram-goals-bot`
- `journalctl -u telegram-goals-bot -f`

Production launch requires a separate test Telegram bot and smoke test.

Manual production deploy procedure:

1. Confirm the target commit/ref and production approval with the user.
2. Confirm GitHub `production` environment approval is enabled.
3. Confirm all deployment secrets exist in GitHub Actions.
4. Run the `Deploy Production` workflow manually with the approved ref.
5. Verify the workflow test gate, VPS install test gate, service restart, and service status.
6. Run the production smoke checklist with test Telegram bot, test Google Sheet, error bot, notification bot, and transcription provider.

Rollback procedure:

1. On the VPS, point `VPS_APP_DIR/current` back to the previous release directory.
2. Restart `VPS_SERVICE_NAME` through GitHub Actions or emergency SSH if production is broken.
3. Record the rollback reason and failed release SHA in project decisions or incident notes.

## Retention and Backups

- SQLite: daily automatic backup, 14-day retention.
- Google Sheets: periodic `.xlsx` or `.csv` export, 14-day retention.
- Audio: no mandatory backup; original audio is deleted one month after recording.
- Failed voice attempts delete the just-downloaded local audio file when processing fails after download.
- PDF: no mandatory separate backup; PDF is stored locally for 6 months after challenge end.
