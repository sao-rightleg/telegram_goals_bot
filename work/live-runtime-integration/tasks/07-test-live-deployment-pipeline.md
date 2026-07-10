---
status: done
depends_on: [6]
wave: 4
skills: [deploy-pipeline]
verify: [smoke]
reviewers: [code-reviewer, security-auditor, deploy-reviewer]
teammate_name:
---

# Task 7: Test-live deployment pipeline

## Required Skills

Before executing the task, load:
- `/skill:deploy-pipeline` - [SKILL.md](/root/.codex/skills/deploy-pipeline/SKILL.md)

## Description

Add separate test-live deployment artifacts for the VPS test environment. The test workflow must not reuse production environment names, production app directory variables, or production service variables in a way that could restart production by mistake.

This task prepares deployment code only. Running the GitHub workflow requires separate explicit user approval.

## What to do

- Add a manual GitHub Actions workflow for test deployment using GitHub environment `test`.
- Add test-specific VPS secret names or a clearly test-scoped workflow environment contract.
- Add a test systemd unit targeting `/opt/telegram_goals_bot_test/current` and `telegram-goals-bot-test.service`.
- Run tests and `check-config` before switching the test `current` symlink.
- Update deployment preparation docs with test-live setup and production-blocking notes.
- Add static/project tooling tests that verify test deploy artifacts do not reference production service/app-dir defaults.

## TDD Anchor

Tests to write BEFORE implementation. Write -> run -> confirm they fail -> write deploy artifacts/docs -> confirm they pass.

- `tests/test_project_tooling.py::test_deploy_test_workflow_uses_test_environment` - workflow environment is `test`.
- `tests/test_project_tooling.py::test_deploy_test_workflow_uses_test_scoped_secrets` - workflow does not use production secret names for app dir/service.
- `tests/test_project_tooling.py::test_test_systemd_unit_targets_test_app_dir_and_service` - unit uses test paths/service naming.

## Acceptance Criteria

- [ ] `.github/workflows/deploy-test.yml` exists and is manual-only.
- [ ] Test deploy workflow uses GitHub environment `test`.
- [ ] Test workflow deploys to the test app dir and restarts only the test service.
- [ ] Production workflow remains unchanged unless documentation-only references are needed.
- [ ] Test systemd unit uses `/opt/telegram_goals_bot_test/current`.
- [ ] Docs explain that production deploy remains blocked until separate approval after test smoke.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [.github/workflows/deploy-production.yml](/root/telegram_goals_bot/.github/workflows/deploy-production.yml)
- [deploy/systemd/telegram-goals-bot.service](/root/telegram_goals_bot/deploy/systemd/telegram-goals-bot.service)
- [docs/09_deployment_preparation.md](/root/telegram_goals_bot/docs/09_deployment_preparation.md)
- [.codex/skills/project-knowledge/references/deployment.md](/root/telegram_goals_bot/.codex/skills/project-knowledge/references/deployment.md)
- [tests/test_project_tooling.py](/root/telegram_goals_bot/tests/test_project_tooling.py)

## Verification Steps

### Automated
- `python -m pytest tests/test_project_tooling.py -v` -> all pass

### Smoke
- `python -m pytest tests/test_project_tooling.py -v` -> all pass

## Details

**Files:**
- `.github/workflows/deploy-test.yml` - manual test deployment workflow.
- `deploy/systemd/telegram-goals-bot-test.service` - test systemd template.
- `docs/09_deployment_preparation.md` - test-live deployment notes.
- `tests/test_project_tooling.py` - static workflow/unit checks.

**Dependencies:** Task 6.

**Edge cases:**
- Workflow accidentally uses `production` environment.
- Workflow accidentally uses production app dir/service secret names.
- Test deploy restarts production service name.
- Direct SSH is documented as normal deploy path; it must not be.

**Implementation hints:**
- Mirror the production workflow structure but use test-scoped names.
- Keep workflow `workflow_dispatch` only.
- Do not embed secrets or concrete tokens in docs or workflow files.

## Reviewers

- **code-reviewer** -> `work/live-runtime-integration/logs/working/task-7/code-reviewer-1.json`
- **security-auditor** -> `work/live-runtime-integration/logs/working/task-7/security-auditor-1.json`
- **deploy-reviewer** -> `work/live-runtime-integration/logs/working/task-7/deploy-reviewer-1.json`

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If you deviated from the spec, describe the deviation and reason.
- [ ] Update user-spec/tech-spec if anything changed.
