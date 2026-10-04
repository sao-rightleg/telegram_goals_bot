# Captain Team About View

Reuse MenuAction.VIEW_TEAM and CaptainService.show_team. Resolve captain through existing private-chat/current-assignment guard; filter rows through existing consenting-active-team member helper with exact flow scope. Read Participants.about_me without additional Sheets calls or schema changes.

Escape both names and user text. Render descriptions with Telegram HTML expandable blockquotes. Split raw description into escaped chunks bounded by serialized HTML and UTF-16-unit budgets, never split entities or tags; emit self-contained cards and combine cards into messages within 3,900 units. Repeat name with continuation marker for oversized descriptions. Use plain missing-profile line when empty. Preserve full profile content and response contracts.

Verify own-team/flow privacy, consent, revoked assignment, empty descriptions, escaping, emoji/large descriptions, fresh reads and existing menu dispatcher routing. Run targeted/full tests and code/security/test reviews. Deployment is a separate user-authorized action.
