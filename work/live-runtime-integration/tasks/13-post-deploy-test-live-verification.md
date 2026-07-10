---
status: planned
depends_on: [12]
wave: 8
skills: [post-deploy-qa]
verify: [user]
reviewers: []
teammate_name:
---

# Task 13: Post-deploy test-live verification

## Required Skills

Before executing the task, load:
- `/skill:post-deploy-qa` - [SKILL.md](/root/.codex/skills/post-deploy-qa/SKILL.md)

## Description

Verify the deployed test-live environment with real test Telegram bots, the test Google Sheet, and Yandex SpeechKit. This task completes the first live smoke only: interactive flows, voice, and captain flow.

Production launch remains blocked after this task until the user gives a separate explicit approval for a later production-hardening/pre-production stage.

## What to do

- Read user-spec, tech-spec, pre-deploy QA report, and deploy report.
- Confirm the test service is the target and production service is not part of the verification.
- Guide or perform the approved manual smoke with test accounts.
- Verify known participant `/start`, consent, role menu, goal, planned steps, progress.
- Verify unknown user gets approved rejection and admin error chat receives sanitized notification.
- Verify weekly report text and insight text write to the test Google Sheet.
- Verify one Russian voice under 10 minutes is transcribed through Yandex and added to the active draft.
- Verify captain sees only own team and can submit one manual report for own-team participant.
- Record pass/fail/deferred status and production-blocking next steps in the report.

## Acceptance Criteria

- [ ] Test service is running and production service is not touched.
- [ ] Known participant smoke passes.
- [ ] Unknown-user rejection and admin notification pass.
- [ ] Weekly report text smoke passes.
- [ ] Insight text smoke passes.
- [ ] Voice transcription smoke passes with Yandex.
- [ ] Captain own-team/manual-report smoke passes.
- [ ] Report states that production deploy remains blocked pending separate approval.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [docs/09_deployment_preparation.md](/root/telegram_goals_bot/docs/09_deployment_preparation.md)
- [work/live-runtime-integration/logs/working/pre-deploy-qa.md](../logs/working/pre-deploy-qa.md)
- [work/live-runtime-integration/logs/working/deploy-test.md](../logs/working/deploy-test.md)

## Verification Steps

### Automated
- Review deploy workflow result and service readiness output from Task 12.

### User
- Run Telegram smoke with test accounts: `/start`, consent, menu, goal, steps, progress, weekly report text, insight text, one voice, captain own-team/manual report.

## Details

**Files:**
- `work/live-runtime-integration/logs/working/post-deploy-qa.md` - write post-deploy verification report.

**Dependencies:** Task 12.

**Edge cases:**
- Test sheet lacks required smoke data.
- Yandex is slow or times out; verify user failure text and admin error.
- Unknown user admin notification includes too much personal data.
- Captain can see or report for another team; this is blocking.
- Live smoke reveals scheduler/report/PDF gaps; those belong to later pre-production unless they block current smoke acceptance.

**Implementation hints:**
- Keep screenshots/log excerpts sanitized.
- Record exact dates/times for smoke actions.
- Do not include bot tokens, API keys, raw credentials, full personal report text, audio contents, or PDF contents in the report.

## Reviewers

None.

## Post-completion

- [ ] Write a brief report in `decisions.md` per the template.
- [ ] If test-live smoke passes, record that production is still blocked until separate explicit approval.
