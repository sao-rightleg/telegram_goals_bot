# Deploy Test: live-runtime-integration

Status: failed
Date: 2026-07-12
Repository: `sao-rightleg/telegram_goals_bot`
Workflow: `Deploy Test`
Run ID: `29183251404`
Run URL: `https://github.com/sao-rightleg/telegram_goals_bot/actions/runs/29183251404`
Approved ref: `c174fd2fd7d38b1b5c549bf256419664105142e1`

## Summary

The user approved test-live deployment through GitHub Actions. The workflow was started for the approved ref and passed all local GitHub runner gates before SSH upload.

The deploy failed at the `Upload archive` step before installing or restarting anything on the VPS.

## Passed Gates

- GitHub environment `test` exists.
- Required test environment secret names exist:
  - `TEST_VPS_HOST`
  - `TEST_VPS_PORT`
  - `TEST_VPS_USER`
  - `TEST_VPS_SSH_KEY`
  - `TEST_VPS_APP_DIR`
  - `TEST_VPS_SERVICE_NAME`
- Workflow input ref: `c174fd2fd7d38b1b5c549bf256419664105142e1`.
- GitHub runner checked out the repository.
- Python setup completed.
- Pre-deploy test suite passed in GitHub Actions.
- Test deployment secret validation passed, including:
  - `TEST_VPS_APP_DIR=/opt/telegram_goals_bot_test`
  - `TEST_VPS_SERVICE_NAME=telegram-goals-bot-test.service`
- Deployment archive was created.
- SSH setup and host key scan completed.

## Failure

Failed step: `Upload archive`

Sanitized failure summary:

```text
Load key "/home/runner/.ssh/deploy_key": error in libcrypto
Permission denied, please try again.
Permission denied, please try again.
***@***: Permission denied (publickey,password).
scp: Connection closed
Process completed with exit code 255.
```

Most likely cause: `TEST_VPS_SSH_KEY` is not a valid unencrypted private key in the format expected by OpenSSH, or it does not match an authorized public key for `TEST_VPS_USER` on `TEST_VPS_HOST`.

## External Actions

- GitHub Actions `Deploy Test` workflow was started.
- No direct SSH/VPS command was run from this workspace.
- The workflow did not reach the install/restart step.
- Production workflow, production service, production secrets, and production app directory were not touched.
- No live Telegram/Google/Yandex smoke was run.

## Next Step

Fix the test deployment SSH credential setup, then rerun `Deploy Test` for ref `c174fd2fd7d38b1b5c549bf256419664105142e1`.

Do not paste secret values in chat. Store the corrected private key only in GitHub environment secret `TEST_VPS_SSH_KEY`, and ensure its matching public key is installed on the VPS for `TEST_VPS_USER`.

## Retry: 2026-07-12

Run ID: `29183791812`
Run URL: `https://github.com/sao-rightleg/telegram_goals_bot/actions/runs/29183791812`

The user updated `TEST_VPS_SSH_KEY` and requested a recheck. The workflow was rerun for the same approved ref.

Result: failed at the same `Upload archive` step.

Passed again:

- GitHub runner checkout.
- Python setup.
- Pre-deploy test suite.
- Test deployment secret validation.
- Archive creation.
- SSH setup and host key scan.

Sanitized failure summary:

```text
Load key "/home/runner/.ssh/deploy_key": error in libcrypto
Permission denied, please try again.
Permission denied, please try again.
***@***: Permission denied (publickey,password).
scp: Connection closed
Process completed with exit code 255.
```

Interpretation: the updated `TEST_VPS_SSH_KEY` still is not parseable by OpenSSH as a private key. This failure happens before a normal public-key authorization check, so the next fix should focus on the exact secret value format.

## Retry: 2026-07-12 via gh secret update

Run ID: `29202403697`
Run URL: `https://github.com/sao-rightleg/telegram_goals_bot/actions/runs/29202403697`

The user reported updating `TEST_VPS_SSH_KEY` through `gh`. The local private key file `~/.ssh/telegram_goals_bot_test` was validated with:

```text
ssh-keygen -y -f ~/.ssh/telegram_goals_bot_test >/dev/null && echo OK
```

Result: `OK`.

The workflow was rerun for the same approved ref.

Result: failed again at `Upload archive`.

Sanitized failure summary:

```text
Load key "/home/runner/.ssh/deploy_key": error in libcrypto
Permission denied, please try again.
Permission denied, please try again.
***@***: Permission denied (publickey,password).
scp: Connection closed
Process completed with exit code 255.
```

Environment secret metadata:

```text
TEST_VPS_SSH_KEY updated_at: 2026-07-12T17:34:44Z
```

Interpretation: the local key file is valid, but the GitHub environment secret value still reaches the runner in a form OpenSSH cannot parse. A direct `gh secret set ... --body-file ~/.ssh/telegram_goals_bot_test --env test` from this authenticated workspace is the next safest fix because it avoids browser copy/paste corruption.

## Retry: 2026-07-12 secret set from workspace

Run ID: `29202529683`
Run URL: `https://github.com/sao-rightleg/telegram_goals_bot/actions/runs/29202529683`

The user approved updating `TEST_VPS_SSH_KEY` directly from this workspace. The installed GitHub CLI does not support `--body-file`, so the equivalent stdin form was used:

```text
gh secret set TEST_VPS_SSH_KEY --repo sao-rightleg/telegram_goals_bot --env test < ~/.ssh/telegram_goals_bot_test
```

Environment secret metadata after update:

```text
TEST_VPS_SSH_KEY updated_at: 2026-07-12T17:43:10Z
```

Result: SSH key parsing and authentication blocker was fixed.

Passed gates:

- GitHub runner checkout.
- Python setup.
- Pre-deploy test suite.
- Test deployment secret validation.
- Archive creation.
- SSH setup and host key scan.
- Archive upload to VPS.
- Remote release install started.
- Remote package install completed.
- Remote VPS test suite passed: `351 passed in 15.41s`.

Failure moved to `check-config` in `Install test release and restart test service`.

Sanitized failure summary:

```text
Missing required settings: MAIN_TELEGRAM_BOT_TOKEN, ERROR_TELEGRAM_BOT_TOKEN, NOTIFICATION_TELEGRAM_BOT_TOKEN, GOOGLE_SHEETS_ID, GOOGLE_APPLICATION_CREDENTIALS, ADMIN_TELEGRAM_ID, ADMIN_ERROR_CHAT_ID, SITNIKOV_TELEGRAM_ID, SQLITE_DB_PATH, AUDIO_STORAGE_DIR, PDF_STORAGE_DIR
Process completed with exit code 2.
```

Interpretation: the deploy key is now correct. The remaining blocker is the test VPS runtime environment file at `/opt/telegram_goals_bot_test/shared/.env`: required runtime settings are missing. The workflow stopped before updating `current` and before restarting `telegram-goals-bot-test.service`.

## Retry: 2026-07-19 credentials configured

Run ID: `29697217640`
Run URL: `https://github.com/sao-rightleg/telegram_goals_bot/actions/runs/29697217640`

The user reported that the Google credentials JSON was configured. The workflow was rerun for the same approved ref.

Passed gates:

- GitHub runner checkout.
- Python setup.
- Pre-deploy test suite.
- Test deployment secret validation.
- Archive creation.
- SSH setup and host key scan.
- Archive upload to VPS.
- Remote release install started.
- Remote package install completed.
- Remote VPS test suite passed: `351 passed in 15.99s`.

Failure remained in `check-config`, but moved from missing required settings to invalid transcription provider value.

Sanitized failure summary:

```text
Setting TRANSCRIPTION_PROVIDER must be one of: fake, yandex
Process completed with exit code 2.
```

Interpretation: required environment values and Google credentials are now present enough to reach provider validation. The test VPS `.env` should use `TRANSCRIPTION_PROVIDER=fake` for test-live without Yandex credentials, or `TRANSCRIPTION_PROVIDER=yandex` with valid Yandex settings.
