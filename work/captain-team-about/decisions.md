# Decisions and Verification

- Reuse the existing captain team button; no duplicate button or schema change.
- Read Participants.about_me and reuse current assignment and eligible-member guards.
- Native Telegram expandable HTML blockquotes, escaped user text.
- Bound serialized UTF-16 lengths, intact entities/tags, complete body text in continuations.
- Names retain the existing display fallback; unusually long names are capped at 200 characters.

## Checks

- Existing captain team/price baseline: 64 passed.
- New profile/escaping/large-description tests failed before implementation.
- Targeted suite including dispatcher, privacy, large teams and existing captain flows: 73 passed.
- Changed files pass Ruff and git diff --check.
- Full suite: 813 passed in 64.60 seconds.
- Code, security and test reviews passed without findings.

## Review Findings

| Source | Finding | Action | Reason |
| --- | --- | --- | --- |
