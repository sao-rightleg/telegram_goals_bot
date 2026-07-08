---
# Creation date (YYYY-MM-DD)
created: 2026-07-08

# Status: draft | approved
status: draft

# Work type: feature | bug | refactoring
type: feature

# Feature size: S (1-3 files, local fix) | M (several components) | L (new architecture)
size: M
---

# User Spec: scheduler-deadlines

## What we're building

Делаем исполнение еженедельного scheduler для MVP: напоминания участникам, закрытие недели по дедлайну, фиксацию `⬜ нет ответа` и уведомления капитанам/трекерам о молчащих участниках.

Фича не включает генерацию PDF, короткие Telegram-отчёты по командам, group comparison и production deploy. Они остаются для отдельных следующих фич.

## Why

Сейчас правила календаря и дедлайна уже описаны и частично представлены в коде, но нет полноценного автоматического исполнения weekly jobs. Без этого администратор должен вручную отслеживать, кто не сдал отчёт, а отчёты могут считать `нет ответа` по-разному.

Эта фича делает дедлайн официальной точкой закрытия недели: после воскресенья 23:59 по Екатеринбургу у каждого активного участника либо есть отчёт, либо создана запись `⬜ нет ответа`.

## How it should work

1. Scheduler использует общий календарь челленджа и timezone `Asia/Yekaterinburg`.
2. В понедельник 10:00, среду 10:00, воскресенье 18:00, воскресенье 22:30 и воскресенье 23:00 scheduler отправляет напоминания только активным участникам, которые дали согласие и ещё не сдали weekly report за текущую неделю.
3. Выбывшие участники не получают обычные напоминания.
4. Участники без согласия не получают напоминания, но если они активны и не сдали отчёт, при закрытии недели им всё равно ставится `⬜`.
5. Воскресенье 18:00 - только текстовое напоминание, что дедлайн близко. Оно не запускает форму отчёта и не показывает кнопки `🟩/🟦/🟥`.
6. Если отправка напоминания одному участнику упала, scheduler продолжает отправку остальным.
7. Для неуспешной отправки одному участнику scheduler делает до 3 попыток. Если после 3 попыток отправить не удалось, он фиксирует failed/skipped в SQLite и отправляет admin error.
8. Следующая плановая рассылка снова может попробовать отправить напоминание этому участнику, если отчёта всё ещё нет.
9. В воскресенье 23:59 scheduler закрывает неделю.
10. При закрытии недели scheduler создаёт в Google Sheets официальный weekly report со статусом `gray` / `⬜` для каждого активного участника, у которого нет финального отчёта за неделю.
11. Если участник начал черновик, но не нажал `✅ Готово` до дедлайна, он всё равно считается молчащим и получает `⬜`. Черновик остаётся в SQLite как техническое состояние/история.
12. Week close должен быть идемпотентным: повторный запуск не создаёт дубликаты и дописывает только недостающие `⬜`.
13. После week close участнику не отправляется отдельное сообщение о том, что неделя отмечена как `⬜`.
14. После week close капитан и трекер получают одно агрегированное сообщение по команде со списком молчащих участников.
15. Если у команды нет капитана или у капитана/трекера нет Telegram chat id, week close всё равно создаёт `⬜`; уведомление для отсутствующего получателя пропускается, а admin получает error.
16. Если участник с незавершённым черновиком после дедлайна нажимает `✅ Готово`, бот показывает существующее сообщение: `Дедлайн недели уже прошёл. Отчёт не может изменить статус.` Черновик остаётся.

Текст агрегированного silent notification:

```text
Нет отчёта за неделю {week_number}: {N} участник(ов).
- {name}
- {name}
```

В MVP в этом сообщении показываем только имена. Статус черновика не раскрываем.

## Acceptance Criteria

- [ ] Scheduler отправляет понедельничное, средовое, воскресное 18:00, воскресное 22:30 и воскресное 23:00 напоминания по утверждённому расписанию в `Asia/Yekaterinburg`.
- [ ] Напоминания отправляются только активным участникам с `consent_given = true`, у которых ещё нет weekly report за текущую неделю.
- [ ] Напоминания не отправляются выбывшим участникам, участникам без согласия и участникам, уже сдавшим weekly report.
- [ ] Воскресенье 18:00 отправляет только текстовое напоминание о близком дедлайне и не запускает weekly report flow.
- [ ] Сбой отправки одному участнику не останавливает отправку остальным участникам.
- [ ] Для одного failed reminder recipient выполняется не больше 3 попыток в рамках одной плановой рассылки.
- [ ] После исчерпания 3 попыток scheduler записывает failed/skipped состояние в SQLite и отправляет admin error.
- [ ] При воскресном week close scheduler создаёт `gray` / `⬜` weekly report в Google Sheets для каждого активного участника без финального weekly report.
- [ ] Active participant без согласия получает `⬜` при week close, если у него нет weekly report.
- [ ] Выбывший участник не получает новую `⬜` запись через week close.
- [ ] Участник с незавершённым черновиком получает `⬜` при week close, а черновик остаётся в SQLite.
- [ ] Повторный запуск week close не создаёт дубликаты weekly reports и дописывает только недостающие `⬜`.
- [ ] Если Google Sheets write падает на середине week close, следующий запуск week close корректно продолжает с недостающих участников.
- [ ] После week close участникам не отправляется отдельное сообщение о `⬜`.
- [ ] Captain получает одно агрегированное silent notification сообщение по своей команде.
- [ ] Tracker получает одно агрегированное silent notification сообщение по назначенной команде.
- [ ] Silent notification содержит только количество и имена молчащих участников, без статуса черновика и без данных других команд.
- [ ] Отсутствующий captain/tracker chat id не блокирует week close; admin получает error о невозможности отправить notification.
- [ ] После дедлайна попытка завершить старый черновик возвращает сообщение `Дедлайн недели уже прошёл. Отчёт не может изменить статус.` и не меняет статус недели.
- [ ] Фича не генерирует PDF, team report, group comparison и не выполняет production deploy.

## Constraints

- Все даты, дедлайны и расписание считаются в `Asia/Yekaterinburg`.
- Жёсткий дедлайн недели: воскресенье 23:59.
- После дедлайна weekly status не меняется.
- Жёлтого late status нет.
- Google Sheets остаётся основным хранилищем бизнес-фактов.
- SQLite хранит только техническое состояние: scheduler jobs, job runs, reminder log, retry state, errors, drafts.
- Нельзя хранить финальные weekly reports только в SQLite.
- Нужно соблюдать разделение трёх ботов: main bot для participant reminders, notification bot для operational notifications, error bot для admin errors.
- Не добавляем Docker, Redis, Celery, PostgreSQL, web form, web admin panel или production deploy в рамках этой фичи.
- Не просим пользователя присылать секреты в чат.

## Risks

- **Risk 1:** Повторный запуск week close может создать дубликаты `⬜`. **Mitigation:** week close должен проверять существующий weekly report по participant/week и создавать только отсутствующие записи.
- **Risk 2:** Сбой Google Sheets на середине закрытия недели может оставить часть участников без финального статуса. **Mitigation:** повторный запуск должен быть идемпотентным и дописывать недостающие `⬜`.
- **Risk 3:** Ошибка отправки одному участнику может остановить всю рассылку. **Mitigation:** отправка и retry должны быть изолированы на уровне participant recipient.
- **Risk 4:** Silent notification может раскрыть данные не той команде или не тому трекеру. **Mitigation:** уведомления агрегируются строго по team/tracker scope, а тесты проверяют отсутствие cross-team leakage.
- **Risk 5:** Текущий `SheetsGateway` может не иметь нужных методов для scheduler. **Mitigation:** tech-spec должен явно описать недостающие queries и fake-boundary покрытие.

## Technical Decisions

- Week close создаёт официальные `gray` / `⬜` weekly reports в Google Sheets, потому что `нет ответа` должен быть бизнес-фактом, а не расчётом на лету.
- Week close делаем идемпотентным, потому что scheduler jobs могут повторяться после сбоев, рестартов и partial Google Sheets failures.
- Незавершённый черновик после дедлайна не удаляем, но он не меняет статус недели.
- Sunday 18:00 - только напоминание о близком дедлайне, без запуска report flow.
- Silent notifications отправляем агрегированно капитану и трекеру, одним сообщением со списком имён.
- В silent notification не показываем статус черновика.
- Для failed reminder recipient используем максимум 3 попытки в рамках одной плановой рассылки.
- Live Telegram bot и test Google Sheets smoke не входят в эту фичу; они будут проверяться на pre-deploy/deployment этапе.

## Testing

**Unit tests:** yes - обязательны для календаря, отбора получателей, форматирования сообщений, retry policy и week close decisions.

**Integration tests:** yes - нужны локальные tests с fake Google Sheets, fake bot clients, fake notification router и временной SQLite базой. Фича затрагивает несколько границ: Sheets, SQLite, notification routing и scheduler.

**E2E tests:** no for this feature - live Telegram/test Google Sheets smoke откладывается до pre-deploy/deployment фичи, потому что здесь не добавляем production deploy и live adapters.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| 1. Run scheduler-related tests | `python -m pytest tests/test_scheduler_foundation.py` | Existing scheduler calendar tests pass. |
| 2. Run new scheduler deadline tests | `python -m pytest tests/test_scheduler_deadlines.py` | Reminder selection, retry policy, week close, gray creation, and silent notifications pass. |
| 3. Run weekly report boundary tests | `python -m pytest tests/test_weekly_report_finalize.py tests/test_weekly_report_boundaries.py` | Existing deadline behavior remains unchanged. |
| 4. Run full local suite | `python -m pytest` | All local fake-boundary tests pass without production secrets. |
| 5. Manual service smoke | `python -c "..."` or focused pytest | A controlled scheduler run with fake participants creates only expected messages and `⬜` rows. |
