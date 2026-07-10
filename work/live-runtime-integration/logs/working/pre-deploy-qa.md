# Pre-deploy QA: live-runtime-integration

Status: passed
Full report: `work/live-runtime-integration/logs/working/pre-deploy-qa.json`

## Summary

- Full pytest: 351 passed in 16.76s.
- Runtime/config/deploy targeted smoke: 71 passed in 3.11s.
- Dependency audit: No known vulnerabilities found.
- Findings: none.
- Deferred to post-deploy: 5 live checks (test VPS launch, real Yandex voice, interactive Telegram smoke, captain smoke, test Google Sheet data).
- No deploy, push, SSH, live Telegram/Google/Yandex, or production action was performed.
