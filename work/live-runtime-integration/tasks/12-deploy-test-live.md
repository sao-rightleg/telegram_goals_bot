---
status: blocked
depends_on: [11]
wave: 7
skills: [deploy-pipeline]
verify: [user]
reviewers: []
teammate_name:
---

# Task 12: Deploy test-live

## Required Skills

Before executing the task, load:
- `/skill:deploy-pipeline` - [SKILL.md](/root/.codex/skills/deploy-pipeline/SKILL.md)

## Description

Deploy the approved feature to the separate test VPS environment through GitHub CI/CD. This task requires explicit user approval before running any external deploy action.

Production service, production app directory, production secrets, and production workflow must remain untouched.

## What to do

- Confirm the exact ref/commit to deploy with the user.
- Confirm the user explicitly approves running the test deploy workflow.
- Confirm GitHub `test` environment and test-scoped secrets are configured.
- Run or instruct the user to run the manual GitHub `Deploy Test` workflow for the approved ref.
- Record workflow result, test service status, and any failure details in the deploy log.
- Do not run production deploy and do not access the server directly unless the user explicitly redirects under the project emergency-debugging rule.

## Acceptance Criteria

- [x] User explicitly approves test-live deploy before the workflow runs.
- [x] Deploy uses GitHub CI/CD, not direct normal SSH.
- [x] Workflow uses GitHub environment `test`.
- [x] Test app dir and test systemd service are used.
- [x] Production service and production secrets are not touched.
- [x] Deploy result is recorded in the working log.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [.github/workflows/deploy-test.yml](/root/telegram_goals_bot/.github/workflows/deploy-test.yml)
- [deploy/systemd/telegram-goals-bot-test.service](/root/telegram_goals_bot/deploy/systemd/telegram-goals-bot-test.service)
- [work/live-runtime-integration/logs/working/pre-deploy-qa.md](../logs/working/pre-deploy-qa.md)

## Verification Steps

### Automated
- Confirm deploy workflow run completed successfully in GitHub Actions.

### User
- User approves and runs the GitHub `Deploy Test` workflow for the selected ref.

## Details

**Files:**
- `work/live-runtime-integration/logs/working/deploy-test.md` - write deployment report.

**Dependencies:** Task 11.

**Edge cases:**
- Test GitHub environment or secrets are missing.
- Workflow fails before upload, during VPS tests, during `check-config`, or during service restart.
- Service starts but immediately exits due to readiness failure.
- User asks to deploy production; this is out of scope and requires separate approval/workflow.

**Implementation hints:**
- Store only workflow metadata and sanitized failure summaries in the report.
- Never request secret values in chat.
- Tell the user where secrets belong: GitHub Actions secrets and protected VPS `.env`.

## Reviewers

None.

## Post-completion

- [x] Write a brief report in `decisions.md` per the template.
- [x] If deploy failed, record blocker and stop before post-deploy smoke.
