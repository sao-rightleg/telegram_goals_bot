---
# Creation date (YYYY-MM-DD)
created: 2026-07-01

# Status: draft | approved
status: draft

# Work type: feature | bug | refactoring
type: feature

# Feature size: S (1-3 files, local fix) | M (several components) | L (new architecture)
size: L
---

# User Spec: mvp-foundation

## What we're building
Создаём технический фундамент MVP Telegram-бота "Трекер целей" без реализации всех пользовательских сценариев целиком.

Фундамент должен подготовить проект к дальнейшей реализации: конфигурация, структура приложения, границы модулей, логирование, SQLite technical state, Google Sheets boundary, три Telegram-бота, scheduler/report/notification boundaries, тестовая основа и smoke-проверки.

## Why
Сейчас проект имеет утверждённую продуктовую документацию, но ещё не имеет рабочей кодовой основы. Если сразу писать пользовательские сценарии, есть риск смешать Telegram handlers, бизнес-логику, Google Sheets, SQLite, отчёты и уведомления в один неуправляемый слой.

Эта фича создаёт устойчивую основу, чтобы следующие фичи реализовывались по согласованной архитектуре и не нарушали ключевые решения MVP: Google Sheets как бизнес-база, SQLite только для технического состояния, `systemd` runtime, три Telegram-бота, role-aware notification routing и отсутствие Docker/PostgreSQL/Redis/Celery в MVP.

## How it should work
1. Разработчик создаёт `.env` по `.env.example` и указывает токены main/error/notification bot, Google Sheets параметры, пути SQLite/audio/PDF и timezone.
2. Приложение может загрузить конфигурацию и проверить обязательные настройки без запуска production-бота.
3. Приложение создаёт или валидирует SQLite schema для технического состояния: dialog drafts, scheduler state, reminder log, technical errors.
4. Приложение имеет отдельные модули/границы для Telegram bot layer, business services, Google Sheets integration, SQLite state, voice processing, report generation, scheduler, notification routing.
5. Main bot, error bot и notification bot представлены как разные runtime clients/config sections, даже если в foundation они ещё не отправляют реальные production-сообщения.
6. Google Sheets integration boundary существует как отдельный слой с безопасными интерфейсами и тестовыми/fake реализациями для разработки.
7. Scheduler foundation знает `Asia/Yekaterinburg`, расписание напоминаний и календарь челленджа, но не обязан сразу выполнять все бизнес-джобы.
8. Report/file storage foundation знает пути `data/audio/`, `data/sqlite/`, `reports/pdf/`, `backups/` и правила retention, но не обязан сразу генерировать финальные PDF.
9. Автоматические тесты проверяют конфигурацию, модульные границы, SQLite schema, basic scheduler calculations и запреты на out-of-MVP инфраструктуру.
10. Agent может локально проверить foundation командами без production deploy.

## Acceptance Criteria
- [ ] Есть понятная Python project structure внутри `app/`, соответствующая архитектуре из `docs/03_architecture.md`.
- [ ] Конфигурация загружается из environment / `.env` и поддерживает отдельные переменные для `MAIN_TELEGRAM_BOT_TOKEN`, `ERROR_TELEGRAM_BOT_TOKEN`, `NOTIFICATION_TELEGRAM_BOT_TOKEN`.
- [ ] Секреты не захардкожены и не выводятся в логи.
- [ ] SQLite technical schema создаётся или валидируется локальной командой.
- [ ] SQLite используется только для technical state, drafts, scheduler state, reminder log, technical errors; бизнес-факты не моделируются как primary storage.
- [ ] Google Sheets integration оформлен как отдельный boundary; production credentials не нужны для unit tests.
- [ ] Notification routing boundary различает main bot, error bot и notification bot.
- [ ] Scheduler foundation использует `Asia/Yekaterinburg`, дату окончания `2026-07-31`, 8 недель + 4 дня итогов и расписание из product decisions.
- [ ] File storage paths и retention constants отражают решения по audio/PDF/backups.
- [ ] В проекте есть тестовая база: unit tests обязательны, integration tests покрывают SQLite schema/config/scheduler foundation.
- [ ] Нет Docker, PostgreSQL, Redis, Celery, Kubernetes или иной out-of-MVP инфраструктуры.
- [ ] README/docs при необходимости обновлены только в части запуска foundation и без изменения продуктовых решений.
- [ ] Локальные smoke-команды позволяют агенту проверить, что foundation запускается и тесты проходят.

## Constraints
- Код пользовательских Telegram-сценариев не должен разрастись за пределы foundation. Полные flows `/start`, consent, weekly report, captain manual report, voice processing, PDF generation и production deploy будут отдельными фичами/задачами.
- Google Sheets остаётся business source of truth. SQLite не должен становиться бизнес-базой.
- Production deployment позже выполняется через GitHub CI/CD и `systemd` на VPS; прямой deploy сейчас не делаем.
- Docker, PostgreSQL, Redis, Celery, Kubernetes не добавлять.
- Не просить пользователя присылать секреты в чат. Секреты должны храниться в `.env` локально и в GitHub Actions secrets для CI/CD.
- Все user-facing тексты в боте остаются на русском; technical docs/code/comments остаются на английском.
- Foundation должен уважать три-ботовую архитектуру и не упрощать её до одного бота без отдельного подтверждения пользователя.

## Risks
- **Risk 1:** Foundation может незаметно начать реализовывать весь MVP сразу. **Mitigation:** ограничить scope инфраструктурой, boundaries, config, SQLite schema и тестовой основой; пользовательские flows вынести в следующие фичи.
- **Risk 2:** SQLite schema может начать дублировать Google Sheets бизнес-данные. **Mitigation:** тестами и архитектурой закрепить SQLite только как technical state.
- **Risk 3:** Три Telegram-бота усложнят foundation. **Mitigation:** на этом этапе сделать явное разделение конфигурации и routing interfaces, а реальные отправки реализовывать постепенно.
- **Risk 4:** Scheduler date calculation может быть неправильно интерпретирован. **Mitigation:** покрыть календарь и `Asia/Yekaterinburg` unit/integration tests.
- **Risk 5:** Секреты могут попасть в логи или репозиторий. **Mitigation:** централизованная config loading, redaction в логировании, `.gitignore`, tests/static checks.

## Technical Decisions
- We decided to build foundation as the first feature because approved docs define a large MVP and the codebase currently has no implementation.
- We decided to keep module boundaries explicit because Telegram handlers must not own business logic or call Google Sheets directly.
- We decided to include SQLite schema/config/scheduler tests in this feature because later flows depend on reliable technical state.
- We decided not to implement full participant/captain/report/voice flows in this feature because each one needs separate user-spec/tech-spec/tasks.
- We decided not to introduce Docker/PostgreSQL/Redis/Celery/Kubernetes because product decisions explicitly exclude them from MVP.
- We decided to preserve the three-bot model because it is a final product decision.

## Testing

**Unit tests:** always done, not up for discussion.

**Integration tests:** yes — foundation touches configuration, SQLite schema, scheduler date logic and file paths, so isolated unit tests are not enough.

**E2E tests:** no for this feature — no complete user-facing Telegram scenario is implemented yet. E2E starts when `/start`, consent or weekly report flows are implemented.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| 1. Run test suite | `pytest` or project test command | All unit and integration tests pass |
| 2. Validate config loading without secrets in logs | local command / test | Missing required env vars fail clearly; loaded config redacts secrets |
| 3. Initialize SQLite schema in temp path | local command / test | Required technical tables exist; no business-storage tables are introduced as primary source |
| 4. Check scheduler constants | unit/integration tests | Timezone is `Asia/Yekaterinburg`; schedule and `2026-07-31` calendar are represented correctly |
| 5. Check project boundaries | static tests / imports | Telegram, services, sheets, storage, scheduler, reports and notification layers are separate |

### User verifies
- Проверить diff и подтвердить, что foundation не реализует лишние MVP-сценарии раньше времени.
- Проверить `.env.example`: переменные понятны, секретные значения отсутствуют, три Telegram-бота отражены явно.
