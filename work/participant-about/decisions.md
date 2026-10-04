# Decisions and Verification

- Optional profile is a Participants.about_me cell, scoped by flow and participant.
- One text answer saves immediately. Append adds a paragraph; replace changes all text.
- Technical state stores flow scope and base/result hashes, never the description.
- User requested this addition after the previous release; deployment is a separate step.

## Review Findings

| Source | Finding | Action | Reason |
| --- | --- | --- | --- |
| Code/test reviewers | Append repeated after an ambiguous successful write | Fixed with durable base/result hashes and Sheets/SQLite failure tests | Prevent duplicate paragraphs |
| Code reviewer | Generic errors lacked actionable context | Added action, Telegram ID and error category without description | Safe operational diagnostics |
| Code reviewer | Duplicated size constants | Shared domain constant and named message chunk size | Consistent validation |
| Security reviewer | Cell coercion changed numeric/boolean descriptions | Preserve literal about_me text, tested live/fake | Exact text survives read/append |
| Test reviewer | Combined-length and empty-prompt gaps | Added 12,000/12,001 boundary and four-topic/button assertions | Cover advertised behavior |

## Checks

- Existing participant view/migration baseline: 28 passed.
- Initial feature tests failed before implementation.
- Focused profile, adapter, SQLite, and existing gateway checks: 74 passed.
- Changed files pass Ruff. Repository-wide Ruff reports six pre-existing unused imports in unrelated insight/report tests; those files remain outside this feature.
- Full test suite: 804 passed in 69.65 seconds.
- Second code, security, and test reviews: approved/passed without remaining findings.
- Migration and live-adapter behavior verified with local API fakes; no deployment or live Telegram sends were performed.
