# Diagnostic Gap Audit

- Prior improvement commit: d3506af, feat: add actionable error bot diagnostics.
- Catalog covered ActionDiagnosticError cases and Telegram polling/ack errors.
- Generic KeyError emitted only exception class and update ID. Successful error-bot delivery left no local incident log.
- Historical incident 798033015 exception arguments/traceback are unavailable. Do not claim a retrospective root cause.
- Preserve privacy: fixed taxonomy, safe app code location, no raw exceptions or payloads.
- Persist already-sanitized notifications in journal even when delivery succeeds.

## Verification

- New diagnostics/privacy/logging tests failed before implementation.
- Targeted diagnostics/runtime/notification suite: 88 passed.
- First full run exposed an unrelated notification polling-format contract; limited new generic metadata to dispatch failures to preserve existing transport messages.
- Final full suite: 819 passed in 73.74 seconds.
- Second code, security and test reviews passed without remaining findings.

## Review Findings

| Source | Finding | Action | Reason |
| --- | --- | --- | --- |

| Code reviewer | Error formatter exceeded 50 lines | Extracted explanation helper | Keep formatter simple |
| Security reviewer | Failed notification logger.exception exposed chained private errors | Use safe logger.error without traceback; added failing chained-exception regression | Preserve privacy in failure path |
| Test reviewer | Generic reason/hint/source assertions were shallow | Assert exact taxonomy and source unavailable for synthetic errors | Detect classification regressions |
