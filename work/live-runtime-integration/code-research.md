# Code Research: live-runtime-integration

## Summary

The repository already contains adapter-independent MVP business services and fake external boundaries. The live-runtime feature should add production/test-live adapters and orchestration around the existing services, not rewrite participant, weekly report, insight, voice, captain, scheduler, or report business rules.

The immediate runtime blocker is explicit: `app/runtime.py` initializes local storage and then raises `RuntimeNotImplementedError` from `run_bot()`.

## Relevant Existing Files

- `app/runtime.py` — CLI entrypoint, storage initialization, current live-runtime stopper.
- `app/config.py` — env loading, strict three-bot token requirements, secret redaction.
- `app/bot/clients.py` — `BotClient`, `TelegramFileDownloader`, fake bot/downloader boundaries.
- `app/sheets/gateway.py` — `SheetsGateway` Protocol and fake in-memory implementation.
- `app/speech/transcription.py` — `SpeechTranscriber` Protocol, `MAX_VOICE_DURATION_SECONDS = 600`, fake transcriber.
- `app/services/participant_flows.py` — `/start`, consent, menu, goal/steps/progress, unknown-user admin notification.
- `app/services/weekly_reports.py` — weekly report draft/status/text/voice/finalization rules.
- `app/services/insights.py` — insight add/list/full-text and voice draft support.
- `app/services/voice_messages.py` — voice download, local storage, transcription, draft append, failure cleanup/admin notification.
- `app/services/captains.py` — captain own-team and manual-report rules.
- `app/services/notifications.py` — three-bot routing model.
- `.github/workflows/deploy-production.yml` — existing production-only manual deploy.
- `deploy/systemd/telegram-goals-bot.service` — production systemd unit template.
- `.env.example` — current env placeholders include transcription provider/key but not Yandex-specific folder/service account settings.

## Existing Patterns to Preserve

- External systems are hidden behind Protocols and fake implementations.
- Business services accept typed user contexts and explicit timestamps.
- Business facts are written through `SheetsGateway`; SQLite stores technical drafts/state.
- Admin errors go through `NotificationRouter` with `NotificationCategory.TECHNICAL_ERROR`.
- Tests use fake boundaries and local SQLite.
- Secrets are loaded from env files/environment and redacted in logs.

## Gaps for This Feature

1. **Telegram live polling and update dispatch are missing.**
   - There is no handler/router layer that maps real Telegram updates, messages, callbacks, and voice metadata into existing services.
   - Need callback/action mapping for menu buttons, weekly report statuses/steps/finalize, insight actions, and captain actions.

2. **Real Telegram bot client/downloader are missing.**
   - `BotClient` and `TelegramFileDownloader` exist only as Protocol/fake.
   - Need concrete client(s) for main/error/notification bots and Telegram file download.

3. **Real Google Sheets adapter is missing.**
   - `SheetsGateway` is Protocol/fake only.
   - Need concrete adapter for all currently required methods.
   - Need fail-fast schema validation for required tabs/columns during `check-config`/startup.

4. **Yandex SpeechKit async adapter is missing.**
   - Current `SpeechTranscriber.transcribe()` is synchronous from service perspective.
   - Recommended MVP approach: implement Yandex async polling inside a concrete adapter with timeout/retry, preserving the existing `SpeechTranscriber` Protocol.
   - If async latency is too long, tech-spec should consider a job-based voice state change, but that is larger and touches more business flow.

5. **Test VPS deploy target is missing.**
   - Existing workflow is production-only and uses GitHub `production` environment.
   - Test live runtime should use a separate VPS app dir/service/env/secrets, or a separate workflow/environment, to avoid production secrets and service restarts.

6. **Runtime composition is missing.**
   - Need factory/composition code that instantiates SQLite repositories, live adapters, notification router, storage policy, and services.
   - Need a long-running process loop with graceful shutdown and crash behavior compatible with systemd.

7. **Schema/config readiness needs extension.**
   - `check-config` currently validates env and SQLite dirs/schema only.
   - Need optional/required live checks: credentials path exists/readable, Google Sheets reachable, required schema present, three Telegram bot tokens valid enough for startup, Yandex config present for `TRANSCRIPTION_PROVIDER=yandex`.

## Risks

- **Callback/state mismatch:** existing services assume correct calls in the correct draft state. Telegram dispatch must recover invalid state safely and notify admin where needed.
- **Yandex async latency:** wrapping async polling inside a synchronous transcriber can make the bot wait during voice handling. Acceptable for test smoke if timeout is bounded; revisit if UX is poor.
- **Schema drift:** Google Sheets manual edits can break runtime. Must fail fast for missing required tabs/columns and tolerate only allowed extra columns.
- **Production/test secret mixing:** a separate test environment is needed so test deploy cannot restart production service or use production tokens/sheets.
- **Dependency creep:** adding SDKs should be minimal and justified. Keep Docker/Redis/Celery/PostgreSQL out of MVP.

## Suggested Test Focus

- Unit tests for Telegram update dispatch into existing services.
- Unit/integration tests for Google Sheets row mapping and fail-fast schema validation with fake sheet data.
- Unit tests for Yandex SpeechKit adapter request/polling/error mapping using mocked HTTP.
- Runtime tests that `telegram-goals-bot run` no longer raises `RuntimeNotImplementedError` when composed with fake/live-testable dependencies.
- Deploy/readiness tests for test environment configuration, without real secrets in repo.
- Manual VPS live-smoke checklist:
  1. Minimum interactive flow: `/start`, known participant, consent, unknown user plus admin error, menu, goal, steps, progress, weekly report text, insight text.
  2. Voice: one Russian voice under 10 minutes through Yandex SpeechKit async into weekly-report or insight draft.
  3. Captain: own-team view plus manual report for own-team participant.
  4. Later pre-production: scheduler, reports, PDF.
