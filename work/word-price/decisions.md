# Word Price Implementation Decisions

## Authorization

The user explicitly approved positive whole RUB input, a participant-linked
Google Sheets tab, and local scenario/code implementation in this conversation.
Production deployment remains a separate approval gate.

## Decisions

- Reuse `steps_setup / awaiting_word_price`; no physical SQLite migration.
- Keep `WordPrices` as the business source, with one immutable declaration per
  `flow_id + participant_id`. Preserve the accepted amount on ambiguous retries.
- Store RAW numeric cells and reject values outside exact integer representation.
- Accept an already pending declaration after the step setup deadline without
  reopening goal or step edits.
- Extend the existing CI/CD business migration to create the tab and headers.

## Review Findings

| Source | Finding | Action | Reason |
| --- | --- | --- | --- |
| Code review | Old cancel/edit callbacks could discard the question or create a new plan | Fixed and tested | Saved steps must remain unchanged while price is pending |
| Code review | Confirmation method grew too large | Extracted `_finish_steps_setup` | Keep confirmation focused on plan persistence |
| Test review | Restart test reused repository instances | Recreated repositories on the existing SQLite file | Verify durable recovery |
| Test review | Missing assertion before weekly focus | Added absence and pending-state assertions | Enforce question ordering |
| Test review | Missing numeric bounds and empty ID cases | Added service/live/fake gateway cases | Validate numeric storage and participant scoping |
| Security review | No actionable findings | Approved | Consent, authorization, RAW writes, bounded input and process-local locking reviewed |

Code review round 2 and test review round 2 passed; security review round 1
passed. JSON reports are retained locally under
`logs/working/task-standalone/` (ignored by Git).

## Verification

- Baseline participant step/view tests: 35 passed.
- New tests demonstrated failures before implementation.
- Full pytest suite after implementation: 749 passed in 62.45 seconds.
- Ruff checks passed for application files and new tests.
- New test files formatted with Ruff; `git diff --check` passed.
- Live `WordPrices` tab creation was completed and read back in the prior turn.
- No live participant messages, Git push, or deployment performed in this turn.

## Follow-up: Price in My Steps

The user requested displaying the declaration when opening `Мои шаги`.
The view now looks up `WordPrices` using both flow and participant IDs and
renders `Цена слова: 5 000 ₽` below progress, or `Цена слова: не указана` when
missing. Parsed numeric output avoids introducing arbitrary Sheets text into
Telegram HTML. Viewing does not change the declaration or planned steps.

Code review identified that adding rendering to the existing menu handler made
it too long; the rendering is now in `_show_planned_steps`, following the
existing view-helper structure. Code review round 2, security review round 1,
and test review round 1 passed. Reports are under
`logs/working/word-price-view/`.

Verification: 78 related tests passed after the extraction, including own-flow
price, foreign participant/flow isolation, setup/working-week views, missing
price, existing step descriptions/buttons and onboarding. Ruff checks, new-test
format validation, and `git diff --check` passed. No deployment performed.

## Follow-up: Captain Team Word Prices

The user requested a captain button labeled exactly `Цена слова участников`.
The action uses the existing private-chat captain authorization and active
assignment checks, lists eligible active consenting own-team members (including
captains), and joins the declarations by flow and participant IDs. Prices are
loaded in one gateway table read rather than one provider call per participant.
Output is sorted plain text with grouped RUB amounts or `не указана`; the
existing sectioned sender handles long lists without splitting participants.
The new action performs no business writes and is inert in direct participant
menu handling.

No code, security, or test review findings were reported. Reports are under
`logs/working/captain-word-prices/`. All 176 related tests passed, covering
captain views/boundaries, menus, real dispatcher routing, Sheets adapters,
missing values, team/flow isolation and long-list delivery. Ruff checks,
new-test format validation and `git diff --check` passed. No deployment performed.
