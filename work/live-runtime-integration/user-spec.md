---
# Creation date (YYYY-MM-DD)
created: 2026-07-09

# Status: draft | approved
status: approved

# Work type: feature | bug | refactoring
type: feature

# Feature size: S (1-3 files, local fix) | M (several components) | L (new architecture)
size: L
---

<!--
This is a scaffold. Section headers below are in English (stable anchors for
validators). Fill the CONTENT in the language the user writes in.
-->

# User Spec: live-runtime-integration

## What we're building
Делаем первый live runtime для тестового запуска Telegram Goals Bot на VPS. Runtime должен подключить реальные Telegram-боты, реальную Google Sheets таблицу, Yandex SpeechKit async для расшифровки голосовых и существующие бизнес-сервисы проекта.

Это не production launch для реальных участников. Цель фичи — запустить тестовую live-среду на VPS с test bot tokens, test Google Sheet и отдельным test systemd service, пройти пошаговый smoke и только после этого готовиться к production.

## Why
Сейчас MVP-срезы реализованы и локально покрыты тестами, но приложение нельзя проверить end-to-end с реальными Telegram updates, Google Sheets и распознаванием речи: команда `telegram-goals-bot run` намеренно падает с ошибкой, что live polling runtime ещё не реализован.

Эта фича снимает главный блокер перед первым реальным запуском: позволяет проверить бота в условиях, близких к production, но без риска для боевых участников, боевой таблицы и production-сервиса.

## How it should work
1. Оператор готовит test VPS environment: отдельную директорию `/opt/telegram_goals_bot_test`, отдельный `telegram-goals-bot-test.service`, GitHub environment `test`, test bot tokens, test Google Sheet, Google service account access и Yandex SpeechKit credentials.
2. GitHub CI/CD выкатывает тестовый runtime на VPS в test environment, не трогая production service, production app dir и production secrets.
3. `telegram-goals-bot --env-file ... check-config` проверяет env, SQLite storage, доступность Google Sheets и наличие всех обязательных вкладок/колонок. Если обязательной вкладки или колонки нет, readiness падает сразу. Лишние колонки в Google Sheets разрешены.
4. `telegram-goals-bot --env-file ... run` запускает долгоживущий Telegram polling process под systemd.
5. Main bot принимает реальные Telegram updates от test accounts и маршрутизирует их в существующие сервисы: `/start`, consent, меню, цель, шаги, прогресс, weekly report, insights, captain flows.
6. Error bot отправляет технические ошибки только в admin error chat. Notification bot остаётся отдельным каналом для операционных уведомлений и будущих report delivery checks.
7. Voice messages до 10 минут скачиваются с Telegram, сохраняются локально на VPS, отправляются в Yandex SpeechKit async, дожидаются результата с bounded timeout и добавляют transcription в active weekly-report или insight draft.
8. Если Yandex SpeechKit не отвечает, возвращает ошибку или превышает timeout, бот не сохраняет failed voice как успешный draft fragment, отвечает пользователю просьбой отправить текстом/повторить и отправляет admin error без секретов и без лишнего персонального текста.
9. Smoke идёт пошагово: сначала минимальные interactive flows, затем voice, затем captain flow, затем более широкий pre-production smoke для scheduler/reports/PDF отдельным следующим этапом.

## Acceptance Criteria
- [ ] Test live runtime запускается на VPS в отдельном окружении: отдельная app dir, отдельный systemd service, отдельный GitHub environment/secrets. Production service и production secrets не используются.
- [ ] `telegram-goals-bot run` больше не падает с `RuntimeNotImplementedError` в test-live конфигурации.
- [ ] Реальные Telegram bot clients реализуют отправку сообщений/документов для main, error и notification bot boundaries.
- [ ] Реальный Telegram file downloader скачивает voice file в локальный audio path по существующей storage policy.
- [ ] Реальный Google Sheets adapter реализует текущий `SheetsGateway` contract для сценариев smoke.
- [ ] `check-config` или startup проверяет обязательные Google Sheets tabs/columns fail-fast. Лишние колонки не блокируют запуск.
- [ ] Если обязательной вкладки/колонки нет, readiness/startup падает до пользовательских сценариев; если error bot уже доступен в runtime path, admin получает sanitized technical error.
- [ ] Yandex SpeechKit async реализован как первый concrete `SpeechTranscriber` provider.
- [ ] `TRANSCRIPTION_PROVIDER=yandex` выбирает Yandex adapter; provider abstraction сохраняется для будущего OpenAI provider.
- [ ] Voice до 10 минут на русском языке успешно расшифровывается через Yandex SpeechKit async и добавляется в active weekly-report или insight draft.
- [ ] Voice timeout/failure не ломает существующий draft, удаляет только failed just-downloaded audio according to current voice rules, отвечает пользователю approved failure text и отправляет sanitized admin error.
- [ ] Минимальный interactive smoke проходит на test bots и test Google Sheet: `/start` known participant, consent, unknown user plus admin error, role menu, goal view, planned steps view, progress view, weekly report text, insight text.
- [ ] Captain smoke проходит вторым шагом: captain видит только свою команду и может внести manual report за участника своей команды.
- [ ] Test Google Sheet содержит минимальные данные: one active team, one participant, one captain, tracker scope, admin/Sitnikov recipients, active goal, six planned steps.
- [ ] Runtime logs and admin errors do not expose bot tokens, API keys, Google credentials, raw secrets, or unnecessary personal report text.
- [ ] Production deploy remains blocked until separate explicit approval after test-live smoke.

## Constraints
Технические и продуктовые ограничения:

- Первый запуск этой фичи только test-live, не production.
- Test runtime должен работать на VPS, не на компьютере пользователя.
- Все deployment actions идут через GitHub CI/CD. Прямой SSH/server access допускается только для emergency debugging broken production, не как обычный deploy path.
- Production deploy нельзя запускать без явного отдельного approval.
- MVP остаётся Telegram-only. Web form не входит в scope.
- Docker, Redis, Celery, PostgreSQL, Kubernetes и web admin panel не добавляются.
- Google Sheets остаётся business storage. SQLite остаётся technical state storage.
- Three-bot model сохраняется: main bot, error bot, notification bot.
- Existing participant, weekly report, insight, voice, captain, scheduler и report business rules не меняются.
- Secrets нельзя писать в чат или репозиторий. Локально/на VPS — protected `.env`/credential files; в CI/CD — GitHub Actions secrets.
- Обязательные Google Sheets tabs/columns должны присутствовать. Extra columns allowed.
- User-facing Telegram messages are in Russian and keep the project tone: short, clear, calm, practical.

## Risks
- **Risk 1:** Test и production secrets/services могут быть случайно смешаны. **Mitigation:** separate GitHub environment `test`, separate VPS app dir, separate systemd service, separate `.env`, separate bot tokens and test sheet.
- **Risk 2:** Yandex SpeechKit async может отвечать медленно. **Mitigation:** bounded timeout, понятный user failure response, admin error, сохранение существующего draft без failed voice fragment.
- **Risk 3:** Google Sheets schema может быть вручную изменена. **Mitigation:** fail-fast schema validation for required tabs/columns before user flows.
- **Risk 4:** Telegram dispatcher может вызвать существующие services в неправильном state. **Mitigation:** tests for callback/update routing, invalid state recovery, admin errors for invalid dialog state.
- **Risk 5:** Logs/admin errors могут раскрыть secrets или персональные тексты. **Mitigation:** reuse redaction patterns, sanitize technical errors, do not include raw tokens, credentials, full report texts, audio contents, or PDF contents.
- **Risk 6:** В feature случайно попадёт production launch. **Mitigation:** user-spec explicitly limits this work to test-live runtime; production launch is a later approval gate.

## Technical Decisions
- We decided to build test-live runtime first because production launch should happen only after smoke on real APIs with test data.
- We decided to run test-live on VPS because the user does not want runtime on their local computer.
- We decided to use a separate test VPS environment because production service and secrets must not be touched during test smoke.
- We decided to use Yandex SpeechKit async as the first speech provider because Russian speech quality and ruble billing are a good MVP fit.
- We decided to keep provider abstraction because OpenAI or another provider may be added later without rewriting voice flows.
- We decided to wrap Yandex async behind the existing synchronous `SpeechTranscriber` contract for the first MVP version because it minimizes changes to existing voice business logic.
- We decided to fail fast on missing required Google Sheets schema because missing required columns are configuration errors, not user-flow edge cases.
- We decided to allow extra Google Sheets columns because admin/tracker manual work may add non-breaking columns.
- We decided not to include production deployment in this feature because production requires separate explicit approval after test-live smoke.

## Testing

**Unit tests:** да, обязательно. Покрыть Telegram update dispatch, callback/action mapping, Google Sheets row mapping/schema validation, Yandex SpeechKit request/polling/error mapping with mocked HTTP, runtime composition, config selection by `TRANSCRIPTION_PROVIDER`.

**Integration tests:** да. Нужны проверки связки runtime composition + fake/live-like adapters + SQLite repositories + existing services, чтобы убедиться, что live layer не ломает уже реализованные business rules.

**E2E tests:** частично manual live smoke на test VPS. Полностью автоматический E2E с реальными Telegram/Yandex/Google secrets не обязателен в этой фиче; отдельный manual GitHub workflow можно добавить позже, если tech-spec покажет, что это безопасно и просто.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| Run test suite | `pytest` | Unit/integration tests pass. |
| Check runtime CLI with test/fake env where applicable | `telegram-goals-bot --env-file ... check-config` | Storage, config, and schema validation pass for valid test config and fail clearly for missing required schema. |
| Verify run command no longer hits not-implemented path | `telegram-goals-bot --env-file ... run` in controlled test/systemd context | Runtime starts polling or reaches expected controlled startup path; no `RuntimeNotImplementedError`. |
| Verify secret redaction | `pytest` / log inspection | Tokens, credentials, API keys are not present in logs or admin error text. |
| Verify test deploy artifacts | GitHub Actions / systemd status | Test deployment uses test environment/service/app dir, not production. |

### User verifies
- На test VPS запущен `telegram-goals-bot-test.service`, production service не затронут.
- В test Telegram bot пройти минимальный smoke: `/start`, consent, menu, goal, steps, progress, weekly report text, insight text.
- От неизвестного Telegram account получить approved rejection text, а в admin error chat увидеть sanitized unknown-user notification.
- Отправить один русский voice до 10 минут в active weekly-report или insight draft; увидеть, что transcription добавился в draft.
- Captain test account видит только свою команду и может внести manual report за own-team participant.
- Перед production launch отдельно подтвердить, что test-live smoke пройден и можно начинать production-hardening/pre-production checks.
