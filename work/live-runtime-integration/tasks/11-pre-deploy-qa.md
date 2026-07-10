---
status: done
depends_on: [8, 9, 10]
wave: 6
skills: [pre-deploy-qa]
verify: [smoke]
reviewers: []
teammate_name:
---

# Task 11: Pre-deploy QA

## Required Skills

Before executing the task, load:
- `/skill:pre-deploy-qa` - [SKILL.md](/root/.codex/skills/pre-deploy-qa/SKILL.md)

## Description

Run acceptance testing before any test-live deployment. This task verifies the local codebase and records which user-spec/tech-spec acceptance criteria are satisfied locally and which are intentionally deferred to post-deploy live smoke.

No deployment, push, or production action is allowed in this task.

## What to do

- Read user-spec, tech-spec, task decisions, and audit reports.
- Run the full local test suite.
- Run targeted runtime/config/deploy artifact smoke checks from the tech-spec.
- Verify acceptance criteria that can be checked without live secrets.
- Record deferred live checks explicitly for Task 13.
- Write the QA report to the working log path.

## Acceptance Criteria

- [x] Full local `pytest` suite passes.
- [x] Runtime/config targeted checks pass.
- [x] Deploy artifact static checks pass.
- [x] Secret redaction and no-real-secret assumptions are checked locally.
- [x] QA report maps acceptance criteria to pass/fail/deferred.
- [x] No deployment or external production action is performed.

## Context Files

- [user-spec.md](../user-spec.md)
- [tech-spec.md](../tech-spec.md)
- [decisions.md](../decisions.md)
- [work/live-runtime-integration/logs/working/code-audit.json](../logs/working/code-audit.json)
- [work/live-runtime-integration/logs/working/security-audit.json](../logs/working/security-audit.json)
- [work/live-runtime-integration/logs/working/test-audit.json](../logs/working/test-audit.json)

## Verification Steps

### Automated
- `python -m pytest -v` -> all pass

### Smoke
- `python -m pytest -v` -> all pass

## Details

**Files:**
- `work/live-runtime-integration/logs/working/pre-deploy-qa.md` - write QA report.

**Dependencies:** Tasks 8-10.

**Edge cases:**
- Audit reports contain unresolved blocking findings.
- Local tests pass but acceptance criteria are only partially covered.
- Live checks require secrets; these must be marked deferred, not faked as passed.
- Production deploy must remain unapproved and untouched.

**Implementation hints:**
- Use a table for acceptance criteria status.
- Include exact commands run and their outcomes.
- Keep report concise but sufficient for post-deploy verification handoff.

## Reviewers

None.

## Post-completion

- [x] Write a brief report in `decisions.md` per the template.
- [x] If QA found blockers, stop before deploy and request/follow a fix task.
