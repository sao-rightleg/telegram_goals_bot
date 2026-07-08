---
# Creation date (YYYY-MM-DD)
created: 2026-07-08

# Status: draft | approved
status: draft

# Work type: feature | bug | refactoring
type: feature

# Feature size: S (1-3 files, local fix) | M (several components) | L (new architecture)
size: L
---

# User Spec: reports-flow

## What we're building

Делаем MVP-блок отчётов после закрытия недели: короткие Telegram-отчёты по командам, PDF-отчёты по командам, полную сводку для админа и Александра Ситникова, а также group comparison только для админа и Александра Ситникова.

Фича включает генерацию отчётов из финальных данных Google Sheets и безопасную доставку через notification bot. Фича не включает production deploy, live Telegram smoke, live Google Sheets smoke, web-интерфейс, публичный leaderboard, coaching recommendations или сложную аналитику.

## Why

После weekly reports и scheduler week close данные уже становятся финальными бизнес-фактами. Капитаны, трекеры, админ и Александр Ситников должны получать недельную картину без ручного чтения Google Sheets и без риска увидеть чужие команды или лишние сравнения.

Главная ценность фичи — role-safe visibility: каждый получатель получает только тот объём данных, который ему разрешён правилами MVP.

## How it should work

1. После закрытия недели scheduler или ручной вызов запускает генерацию отчётов за конкретную неделю.
2. Система читает финальные бизнес-данные из Google Sheets: participants, teams, trackers, goals, planned steps, weekly reports, weekly report step relations, insights.
3. Для каждой команды система формирует короткий Telegram team summary:
   - номер недели;
   - название команды;
   - капитан;
   - активные и выбывшие участники;
   - процент побед недели по активным участникам;
   - список участников с progress bar и процентом прогресса.
4. Для каждой команды система формирует PDF team report:
   - первая страница с summary команды;
   - распределение статусов недели;
   - участники в risk zone;
   - отдельный блок dropped participants;
   - секции участников с weekly status, progress, goal, planned/completed steps, report text, voice transcription, insights.
5. Для админа и Александра Ситникова система формирует full summary по всем командам.
6. Для админа и Александра Ситникова система формирует group comparison. Captains и trackers group comparison не получают.
7. Доставка идёт через notification bot:
   - капитан получает Telegram summary и PDF только своей команды;
   - Ivan Larkin получает отчёты мужских команд;
   - Maria получает отчёты женских команд;
   - админ получает все team reports, all PDFs, full summary, group comparison и ошибки;
   - Александр Ситников получает все team reports, all PDFs, full summary и group comparison.
8. Если у одного получателя нет Telegram chat id или отправка ему падает, система уведомляет admin error bot и продолжает доставку другим разрешённым получателям.
9. Если генерация PDF или summary падает для одной команды, система уведомляет admin error bot и продолжает обрабатывать остальные команды, где это возможно.
10. Повторный запуск генерации/доставки за ту же неделю должен быть идемпотентным: не создавать лишних PDF-файлов без необходимости и не дублировать успешно отправленные отчёты одному и тому же получателю.

## Acceptance Criteria

- [ ] Short Telegram team summary формируется для каждой команды за выбранную неделю.
- [ ] Short Telegram team summary содержит номер недели, team name, captain name, active count, dropped count, weekly victory percent, список участников с progress bar и progress percent.
- [ ] PDF team report формируется для каждой команды и сохраняется в локальный непубличный `reports/pdf/` path.
- [ ] PDF team report содержит первую страницу summary, status distribution, risk zone, dropped participants и participant sections.
- [ ] Participant section содержит имя, username если есть, weekly status, progress bar, progress percent, goal, goal value, permission condition, planned/completed steps, report text, transcription text если есть, insights.
- [ ] Dropped participants остаются видимыми в отчётах, но исключаются из active victory percentage.
- [ ] `green`, `blue`, `red`, `gray` считаются по утверждённым score rules; yellow late status не используется.
- [ ] Main progress percent считается по planned steps, а insights не меняют progress и weekly status.
- [ ] Reports используют Google Sheets final business facts и не читают незавершённые SQLite drafts как report content.
- [ ] Если original audio уже удалён retention cleanup, отчёт показывает `transcription_text` и не пытается открыть или отправить удалённый audio file.
- [ ] Captain получает только Telegram summary и PDF своей команды.
- [ ] Captain не получает чужие команды, full summary или group comparison.
- [ ] Tracker получает только отчёты назначенных команд по gender/team scope.
- [ ] Ivan Larkin получает male team reports; Maria получает female team reports.
- [ ] Tracker не получает group comparison.
- [ ] Admin получает все team reports, all PDFs, full summary, group comparison и report generation/sending errors.
- [ ] Alexander Sitnikov получает all reports, all PDFs, full summary и group comparison.
- [ ] Group comparison отправляется только admin и Alexander Sitnikov.
- [ ] Missing recipient chat id не блокирует доставку другим получателям; admin получает technical error.
- [ ] Send failure одному получателю не блокирует доставку другим получателям; admin получает technical error.
- [ ] PDF generation failure по одной команде не скрывается и не ломает генерацию других команд; admin получает technical error.
- [ ] Повторный запуск за ту же неделю не дублирует уже успешно отправленные отчёты одному recipient.
- [ ] Report generation/send status фиксируется как technical state; финальные business facts остаются в Google Sheets.
- [ ] Generated PDFs, SQLite DBs, logs, credentials и secrets не коммитятся.
- [ ] Фича не добавляет Docker, Redis, Celery, PostgreSQL, web admin panel, public leaderboard или production deploy.

## Constraints

- User-facing report text is Russian.
- Google Sheets остаётся источником финальных business facts.
- SQLite может хранить только technical state: report job/run/send status, retry/idempotency/error metadata.
- PDF files are local, non-public, and must not be exposed by public links.
- PDF files are retained for 6 months after challenge end.
- Notification bot handles report delivery.
- Error bot handles technical admin errors.
- Main bot must not be used for mass report delivery.
- Captains and trackers must not receive group comparison.
- No live external credentials are required in this feature.
- No secrets must be requested in chat.

## Risks

- **Risk 1:** Report routing leaks another team’s personal data. **Mitigation:** Build recipient scopes from team/tracker rules and cover captain/tracker/admin/Sitnikov routing in tests.
- **Risk 2:** Group comparison is accidentally sent to captains or trackers. **Mitigation:** Treat group comparison as admin/Sitnikov-only report type with explicit tests.
- **Risk 3:** Reports include unfinished SQLite drafts. **Mitigation:** Read only Google Sheets final facts for report content.
- **Risk 4:** Duplicate scheduler/report reruns spam recipients. **Mitigation:** Store send status/idempotency keys in technical state and skip already successful sends.
- **Risk 5:** PDF generation fails silently. **Mitigation:** Record failure, notify admin, and keep processing other teams where possible.
- **Risk 6:** Generated PDFs or credentials get committed. **Mitigation:** Use existing storage path policy, `.gitignore`, and pre-deploy artifact scans.

## Technical Decisions

- Reports are generated from Google Sheets final facts, not SQLite drafts, because reports must reflect official weekly status.
- PDF files are generated locally under `reports/pdf/` and delivered as files through notification bot boundaries because public links are not allowed.
- Report generation and report delivery are tracked as technical state for idempotency and retries.
- Short Telegram summary and PDF team report are generated per team; full summary and group comparison are generated globally.
- Group comparison is visible only to admin and Alexander Sitnikov.
- Delivery failures are recipient-isolated so one bad chat id does not block other authorized recipients.
- Live Telegram, live Google Sheets, and production deploy are deferred to deployment/post-deploy work.

## Testing

**Unit tests:** yes - обязательны для расчётов progress/victory percent, status distribution, report formatting, recipient resolution, idempotency keys, and privacy filters.

**Integration tests:** yes - нужны локальные tests с fake Google Sheets, fake report generator/PDF renderer, fake notification bot, fake error bot, temporary SQLite, and local path policy.

**E2E tests:** no for this feature - live Telegram document sending, live Google Sheets, and production runtime checks belong to deployment/post-deploy verification.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| 1. Run report formatting tests | `.venv/bin/python -m pytest tests/test_reports_messages.py tests/test_reports_generation.py` | Telegram summary, PDF data model, status distribution, progress, and dropped participant rules pass. |
| 2. Run report routing tests | `.venv/bin/python -m pytest tests/test_reports_delivery.py` | Captain/tracker/admin/Sitnikov recipients receive only allowed report types. |
| 3. Run report storage/idempotency tests | `.venv/bin/python -m pytest tests/test_reports_repository.py tests/test_sqlite_schema.py` | Report run/send state prevents duplicate sends and stores technical state only. |
| 4. Run report boundary tests | `.venv/bin/python -m pytest tests/test_reports_boundaries.py` | Missing chat id, send failure, PDF generation failure, deleted audio path, no secrets/generated artifacts covered. |
| 5. Run full local suite | `.venv/bin/python -m pytest` | All local tests pass without production secrets or live external services. |
