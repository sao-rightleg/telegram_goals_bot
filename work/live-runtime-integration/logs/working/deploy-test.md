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
