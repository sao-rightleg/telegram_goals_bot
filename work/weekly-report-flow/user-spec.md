---
created: 2026-07-02
status: approved
type: feature
size: M
---

# User Spec: weekly-report-flow

## What we're building

Реализуем service-level flow для недельного отчёта участника: выбор статуса недели `🟩 / 🟦 / 🟥`, выбор связанных planned steps когда это обязательно, сбор текстового отчёта, сохранение финального WeeklyReport в Google Sheets и очистку SQLite draft state.

Фича должна дать участнику возможность зафиксировать результат недели до дедлайна, но не должна пока реализовывать voice processing, scheduler reminders, автоматический `⬜` no-answer статус, captain manual report, insights, PDF, live Telegram SDK, live Google API adapter или production deploy.

## Why

`participant-core-flows` уже даёт безопасный вход, consent, меню и read-only views, но участник всё ещё не может отправить основной недельный отчёт, который влияет на weekly status и planned-step progress.

Эта фича добавляет главный business write путь MVP: участник фиксирует победу, частичный прогресс или отсутствие победы, а финальные факты сохраняются в Google Sheets как source of truth.

## How it should work

1. Недельный отчёт стартует из service-level entry point, который позже сможет вызвать Telegram handler, reminder button или scheduler. В рамках этой фичи live Telegram wiring не делаем.
2. Сервис идентифицирует пользователя по Telegram ID через Google Sheets boundary.
3. Если пользователь неизвестен или не дал consent, flow не продолжается и используется уже существующее safe handling из participant core flows.
4. Сервис определяет текущую неделю и дедлайн по `Asia/Yekaterinburg`.
5. Если дедлайн недели уже прошёл, бот отвечает: `Дедлайн недели уже прошёл. Отчёт не может изменить статус.` и не пишет final weekly status.
6. Если отчёт за эту неделю уже сохранён, бот не создаёт дубль и сообщает, что отчёт уже принят.
7. Если у участника нет активной цели или planned steps, бот не падает:
   - пользователь получает короткое нейтральное сообщение о незаполненных данных;
   - admin error chat получает technical missing-data notification без секретов.
8. При старте flow бот показывает оставшиеся незакрытые planned steps и предлагает выбрать статус:
   - `🟩 Победа есть`
   - `🟦 Частично`
   - `🟥 Победы нет`
9. Если участник выбирает `🟩 Победа есть`:
   - бот требует выбрать один или несколько open planned steps;
   - если шаги не выбраны, финальный отчёт не сохраняется;
   - после выбора шагов бот спрашивает: `Что именно ты сделал?`;
   - участник может отправить один или несколько текстовых сообщений;
   - после `✅ Готово` сервис сохраняет WeeklyReport со status `green` / `🟩` / score `1`;
   - сохраняет WeeklyReportSteps relation `closed` для выбранных шагов;
   - переводит выбранные planned steps в `closed`;
   - не отмечает финальную цель достигнутой автоматически;
   - очищает SQLite draft;
   - отвечает: `Принято. Победа недели сохранена.`
10. Если участник выбирает `🟦 Частично`:
    - бот требует выбрать один или несколько planned steps с частичным прогрессом;
    - если шаги не выбраны, финальный отчёт не сохраняется;
    - бот спрашивает: `Что получилось сделать частично?`;
    - затем может запросить: `Что не хватило до полноценной победы?`;
    - после `✅ Готово` сервис сохраняет WeeklyReport со status `blue` / `🟦` / score `0.5`;
    - сохраняет WeeklyReportSteps relation `partial` для выбранных шагов;
    - planned steps не переводятся в `closed`;
    - очищает SQLite draft;
    - отвечает: `Принято. Частичная победа сохранена.`
11. Если участник выбирает `🟥 Победы нет`:
    - бот спрашивает: `Что помешало сделать победу недели?`;
    - выбранные planned steps не обязательны;
    - после `✅ Готово` сервис сохраняет WeeklyReport со status `red` / `🟥` / score `0`;
    - WeeklyReportSteps relations не обязательны;
    - planned steps не закрываются;
    - очищает SQLite draft;
    - отвечает: `Принято. Отчёт за неделю сохранён.`
12. Пока draft активен:
    - текстовые сообщения сохраняются в SQLite draft state с порядком сообщений;
    - финальный `report_text` собирается в том же порядке;
    - voice messages не принимаются в этой фиче и должны получить короткое сообщение, что голосовые будут доступны позже.
13. Если участник нажимает `✅ Готово` без текстового содержимого:
    - финальный WeeklyReport не создаётся;
    - бот просит отправить текст отчёта.
14. Если SQLite draft state повреждён или устарел:
    - сервис не сохраняет финальные facts;
    - очищает unsafe state;
    - возвращает пользователя в меню или сообщает safe recovery message;
    - admin error chat получает technical notification.

## Acceptance Criteria

- [ ] Weekly report flow идентифицирует участника по Telegram ID через Google Sheets boundary.
- [ ] Flow не продолжается для unknown user или пользователя без consent.
- [ ] Flow использует `Asia/Yekaterinburg` deadline и не сохраняет status-changing report после Sunday 23:59.
- [ ] Повторная отправка отчёта за ту же неделю не создаёт duplicate WeeklyReports.
- [ ] Start flow показывает оставшиеся незакрытые planned steps и status buttons `🟩`, `🟦`, `🟥`.
- [ ] `green` требует один или несколько выбранных open planned steps.
- [ ] `green` сохраняет WeeklyReport со status `green`, symbol `🟩`, score `1`.
- [ ] `green` сохраняет WeeklyReportSteps relation `closed` и закрывает выбранные planned steps.
- [ ] `blue` требует один или несколько выбранных planned steps.
- [ ] `blue` сохраняет WeeklyReport со status `blue`, symbol `🟦`, score `0.5`.
- [ ] `blue` сохраняет WeeklyReportSteps relation `partial` и не закрывает planned steps.
- [ ] `red` не требует selected planned steps.
- [ ] `red` сохраняет WeeklyReport со status `red`, symbol `🟥`, score `0`.
- [ ] `red` не закрывает planned steps.
- [ ] `✅ Готово` без текстового содержимого не создаёт WeeklyReport.
- [ ] Ordered text draft messages собираются в финальный `report_text` в правильном порядке.
- [ ] Финальные WeeklyReports и WeeklyReportSteps пишутся только в Google Sheets boundary.
- [ ] SQLite хранит только technical draft/dialog state и очищается после успешного save.
- [ ] Missing active goal / planned steps не приводит к crash и отправляет safe admin error notification.
- [ ] Bot не отмечает final goal achieved автоматически.
- [ ] Voice messages, insights, captain manual report, scheduler reminders, automatic gray no-answer closure, PDF, live Telegram SDK, live Google API adapter и production deploy не реализуются в этой фиче.
- [ ] Unit/integration tests проходят без production Telegram token и Google credentials.

## Constraints

- User-facing Telegram messages must be in Russian.
- Google Sheets remains the business source of truth.
- SQLite stores only technical draft/dialog state.
- Main bot handles participant interaction.
- Error bot handles technical errors only.
- No production deploy, push, live Telegram messages, or real secrets without separate approval.
- No Docker, PostgreSQL, Redis, Celery, Kubernetes, web admin panel, or web form in MVP.
- Voice transcription is out of scope for this feature even though the final product supports voice.
- Scheduler/reminder triggering is out of scope; this feature exposes service-level weekly report behavior for future wiring.

## Risks

- **Risk 1:** фича может разрастись в scheduler, reminders, gray no-answer closure или captain manual report. **Mitigation:** оставить только participant-submitted text weekly report before deadline; остальные сценарии отдельными фичами.
- **Risk 2:** green/blue могут закрыть неправильные шаги или шаги другого участника. **Mitigation:** все выбранные step IDs валидировать через participant_id и active goal.
- **Risk 3:** можно случайно создать duplicate weekly report. **Mitigation:** проверять существующий WeeklyReport для participant/week перед final save.
- **Risk 4:** SQLite draft может стать business storage. **Mitigation:** хранить в SQLite только draft/session/message state до final save, а финальные факты писать в Google Sheets.
- **Risk 5:** late report может изменить статус закрытой недели. **Mitigation:** deadline guard до final save; late status-changing save запрещён в этой фиче.

## Technical Decisions

- We decided to scope this feature to participant text weekly report submission because this is the next MVP business-write path after participant core flows.
- We decided to keep live Telegram SDK and live Google API adapter out of scope because current architecture uses service-level boundaries and fakes for local verification.
- We decided to store draft report state in SQLite and final report facts in Google Sheets because this follows the approved storage boundary.
- We decided to exclude voice messages because voice processing needs audio storage, transcription, and privacy handling as a separate feature.
- We decided to exclude scheduler reminders and automatic gray status because scheduler behavior and no-answer closure need separate idempotency and deadline processing.
- We decided not to auto-achieve final goals when all planned steps are closed because final goal achievement is fixed by tracker/admin in Google Sheets.

## Testing

**Unit tests:** always done, not up for discussion.

**Integration tests:** yes — фича связывает participant identity/consent, Sheets fake, SQLite draft state, status validation, deadline logic, final report writes и planned-step updates.

**E2E tests:** no — live Telegram bot, live Google Sheets and scheduler/reminder wiring are out of scope for this user-spec.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| Run full test suite | `.venv/bin/python -m pytest -v` | All tests pass without production secrets |
| Verify green report | pytest integration test with fake Sheets and temp SQLite | WeeklyReport saved as green/🟩/1, selected steps closed, draft cleared |
| Verify blue report | pytest integration test | WeeklyReport saved as blue/🟦/0.5, partial step relations saved, steps not closed |
| Verify red report | pytest integration test | WeeklyReport saved as red/🟥/0 without selected steps |
| Verify empty draft finalization | pytest integration test | no WeeklyReport is created; user is asked to send report text |
| Verify deadline guard | pytest unit/integration test | after Sunday 23:59 Yekaterinburg status-changing report is rejected |
| Verify duplicate guard | pytest integration test | second report for same participant/week is rejected |
| Verify storage boundary | static/test checks | final facts only in Sheets fake; SQLite contains only technical state |
| Verify out-of-scope boundaries | static/test checks | no voice, scheduler, PDF, deploy, live SDK, captain manual report, or insight submission added |

### User verifies

- Проверить `user-spec.md` и подтвердить, что scope ограничен participant text weekly report flow.
- Проверить русские тексты статусов, вопросов и подтверждений на соответствие тону проекта.
