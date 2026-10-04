# Initial Word Price Collection

## Scope and Authorization

The user approved positive integer RUB input, a separate participant-linked
Sheets tab, and implementation of the scenarios and code in this conversation.
Existing architecture, report formats, and deployment approval policy apply.

## Implementation

- `ParticipantFlowService` prompts after initial eight-step confirmation.
- Persist only `steps_setup / awaiting_word_price` in the existing SQLite dialog
  state. The existing dispatcher already routes step-setup text to this service.
- Parse ASCII decimal digits, surrounding whitespace, and leading zeros. Reject
  non-positive/fractional/text inputs and numbers above `2^53 - 1`, the technical
  integer precision limit of the numeric Sheets cell.
- Recheck the current-flow participant, consent, role, active status, team, active
  goal, and completed initial plan before saving. The setup deadline does not
  prevent answering an already pending price question.
- Add gateway lookup/save methods for `WordPrices` with composite key
  `(flow_id, participant_id)` and columns `word_price_rub`, `created_at`, `updated_at`.
- Use RAW numeric writes. Serialize check-and-append with the existing reentrant
  Google request lock in the single process. Preserve the first declaration on retries.
- Resume on `/start` or `/menu`; guard stale edit/cancel callbacks.
- Ask for current-week focus only after save; acknowledge the saved amount.
- Extend business-schema migration and startup validation for the new tab.
- Existing participants are not forced into a new backfill interview.
- In the participant steps view, look up the declaration using both flow and
  participant IDs; render a grouped RUB amount or `Цена слова: не указана` below
  progress. This read does not change the amount, step statuses, or report buttons.
- Add `VIEW_TEAM_WORD_PRICES` to the captain-only menu and dispatch it to
  `CaptainService.show_team_word_prices`. Reuse private-chat/active-assignment
  authorization, filter eligible own-team and own-flow participants, and join
  bulk-loaded word prices by flow and participant IDs. Send sorted plain text
  with missing markers and existing sectioned-response splitting.

## Verification

Tests use real SQLite and fake Telegram/Sheets boundaries, including the live
Sheets adapter with a fake provider. Cover validation, ordinary/late/captain
setup, restart, invalid scope, consent/role/status restrictions, ambiguous write
failure, retries, concurrent saves, stale callbacks, Telegram dispatch, and
migration idempotency. Run the full pytest suite and independent code/security/
test reviews. No live bot calls or deployment are authorized by this task.
