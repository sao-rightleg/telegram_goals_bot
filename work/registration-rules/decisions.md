# Registration Rules Decisions

The user supplied and approved the exact rules message in the current request.
It is sent as static Telegram HTML after registration success and before late
goal setup. Wording, paragraph breaks and both underline spans are preserved.
Existing registration completion semantics prevent resending on normal repeated
confirmation or `/start`. No storage schema changes or enforcement automation.

## Review Findings

| Source | Finding | Action | Reason |
| --- | --- | --- | --- |
| Code review | Confirmation method exceeded the method-size guideline | Extracted `_finish_registration` | Separate finalization ownership from response and onboarding continuation |
| Security review | No findings | Approved | Static HTML, no dynamic text, existing consent/registration gates |
| Test review | No findings | Passed | Ordinary/late participant/captain output order and no duplicate sends covered |

Code review round 2, security review round 1 and test review round 1 passed.
Reports are retained in `logs/working/registration-rules/` (Git-ignored).

## Verification

- Baseline registration tests: 57 passed.
- Four new ordering scenarios failed before implementation and passed afterward.
- Related registration/message tests after extraction: 71 passed.
- Ruff checks, new-test format check and `git diff --check` passed.
- No external participant messages, push, or deployment performed.
