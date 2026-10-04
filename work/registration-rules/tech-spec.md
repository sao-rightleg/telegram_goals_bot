# Registration Rules Message

## Authorization and Scope

The user supplied the exact copy and requested a separate message immediately
after successful registration. Existing storage schemas and architecture apply.

## Implementation

- Store static Russian text in `PROJECT_RULES_TEXT` in `app/bot/messages.py`.
- Send through the Main bot using `TELEGRAM_HTML_PARSE_MODE` after the successful
  registration response in `ParticipantFlowService.confirm_registration`.
- Keep both static `<u>` spans, paragraph breaks, wording and punctuation.
- Send before entering the late-registration goal creation flow.
- Use the existing completed-registration path to avoid duplicate onboarding
  messages on repeated confirmations or `/start`.
- No new business storage, SQLite state, payment or exclusion automation.

## Verification

Use real SQLite with fake Telegram/Sheets boundaries. Cover ordinary/late
registration for participants and captains, output order, parse mode, recipient,
content anchors and repeated-start/confirmation behavior. Run related startup,
message and registration tests and independent code/security/test reviews.
