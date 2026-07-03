---
# Creation date (YYYY-MM-DD)
created: 2026-07-03

# Status: draft | approved
status: approved

# Work type: feature | bug | refactoring
type: feature

# Feature size: S (1-3 files, local fix) | M (several components) | L (new architecture)
size: M
---

# User Spec: captain-flows

## What we're building

Добавляем капитанские Telegram-флоу для MVP: капитан видит действия капитана в меню, может посмотреть участников своей команды и вручную отправить weekly report за участника своей команды до дедлайна.

Фича не создает отдельный web-интерфейс и не дает капитану доступ к Google Sheets. Капитан работает только через Telegram-бота. Итоговый ручной отчет капитана сохраняется в те же Google Sheets business-факты weekly report, что и обычный отчет участника, но с корректным источником: `submitted_by_id` = ID капитана, `submitted_by_role` = `captain`.

## Why

Если участник молчит или не может сам отправить отчет, капитан должен закрыть операционный пробел по своей команде до дедлайна. При этом капитан не должен видеть или менять данные других команд и не должен обходить правила статусов, шагов, дедлайна и duplicate guard.

## How it should work

1. Капитан проходит обычный `/start`, identification и consent flow.
2. В меню капитана появляются капитанские действия: посмотреть свою команду и добавить ручной weekly report за участника своей команды.
3. Капитан открывает список участников своей команды.
4. Бот показывает только участников команды капитана, без участников других команд.
5. Капитан выбирает участника своей команды для ручного отчета.
6. Бот проверяет, что участник не выбывший, относится к команде капитана, имеет нужные данные для weekly report и что отчет за текущую неделю еще не существует.
7. Капитан выбирает weekly status: `🟩`, `🟦` или `🟥`.
8. Для `🟩` и `🟦` капитан обязан выбрать один или несколько planned steps участника; уже закрытые шаги нельзя закрыть повторно.
9. Капитан отправляет текст отчета. Если voice input доступен в этом draft-флоу, голосовые до 10 минут должны обрабатываться по тем же правилам voice-processing; если voice не подключен в первом task slice, бот должен явно и безопасно просить текст.
10. Капитан нажимает `✅ Готово`.
11. До дедлайна бот сохраняет weekly report и related weekly_report_steps в Google Sheets.
12. После Sunday 23:59 `Asia/Yekaterinburg` капитан не может сохранить status-changing manual report за закрытую неделю.
13. Технические ошибки уходят только в admin error chat через error bot.

## Acceptance Criteria

- [ ] Только пользователь с ролью `captain` видит и запускает капитанские действия.
- [ ] Капитан видит только участников своей команды.
- [ ] Капитан не может выбрать участника другой команды даже через поддельный callback/ID.
- [ ] Капитан не может отправить ручной отчет за выбывшего участника.
- [ ] Капитан не может отправить второй weekly report за участника и неделю, если отчет уже есть.
- [ ] Капитан не может сохранить manual report после Sunday 23:59 `Asia/Yekaterinburg`, если это меняет weekly status закрытой недели.
- [ ] Для `🟩` капитан обязан выбрать один или несколько закрытых planned step IDs.
- [ ] Для `🟦` капитан обязан выбрать один или несколько related planned step IDs с partial progress.
- [ ] Для `🟥` step selection не требуется и weekly_report_steps не создаются.
- [ ] Уже закрытые planned steps нельзя закрыть повторно через капитанский отчет.
- [ ] Финальный weekly report сохраняет participant_id выбранного участника, team_id его команды, selected status, report text, score и week_number.
- [ ] Финальный weekly report сохраняет `submitted_by_id` как participant_id капитана и `submitted_by_role` как `captain`.
- [ ] Капитанский manual report не меняет инсайты и не создает отдельный тип business-факта вне weekly reports.
- [ ] Техническое состояние выбора участника, статуса, шагов и черновика хранится только в SQLite до успешного финального сохранения.
- [ ] После успешного сохранения технический draft очищается.
- [ ] При ошибке Google Sheets или SQLite draft не превращается в финальный факт, а техническая ошибка уходит только в admin error chat.
- [ ] Участникам, другим капитанам, трекерам и Александру Ситникову технические детали ошибок не отправляются.
- [ ] Фича не добавляет web form, PostgreSQL, Docker, Redis, Celery, web admin panel, participant-created steps, редактирование прошлых недель или late/yellow status.

## Constraints

- MVP канал остается только Telegram.
- Google Sheets остается финальным business storage.
- SQLite хранит только technical state и draft state.
- Все дедлайны считаются в `Asia/Yekaterinburg`.
- Капитан может работать только со своей командой.
- Капитан не получает прямой доступ к Google Sheets.
- Капитан не получает group comparison.
- Для `green` и `blue` обязательна step selection.
- Late status не существует.
- Secrets и production credentials не требуются для локальной разработки этой фичи.

## Risks

- **Risk 1:** Капитан может получить доступ к участнику другой команды через callback tampering. **Mitigation:** все selected participant IDs проверять на серверной стороне через Google Sheets данные, не доверять callback payload.
- **Risk 2:** Капитанский manual report может обойти weekly deadline или duplicate guard. **Mitigation:** финальное сохранение должно использовать те же календарные и duplicate правила, что participant weekly report, с отдельной проверкой роли/selected participant.
- **Risk 3:** Step selection может закрыть уже закрытый шаг повторно. **Mitigation:** фильтровать available steps и проверять выбранные IDs перед save.
- **Risk 4:** Business facts могут остаться только в SQLite. **Mitigation:** SQLite хранит только draft; финальный weekly report и relations пишутся в Google Sheets.
- **Risk 5:** Ошибки Google Sheets могут раскрыть данные участника не тем ролям. **Mitigation:** user-facing copy остается безопасной, technical details идут только в admin error chat.

## Technical Decisions

- We decided to model captain manual report as a weekly report submitted by a captain, not as a separate business fact type.
- We decided to keep Google Sheets as the final storage for captain manual reports because reports and later weekly summaries must read one weekly report model.
- We decided to keep captain selected participant and draft state in SQLite because it is technical dialog state.
- We decided to preserve the existing weekly status semantics: `green = 1`, `blue = 0.5`, `red = 0`, no late/yellow status.
- We decided not to implement captain PDF access in this feature unless the tech spec explicitly scopes it; report delivery belongs to the reports phase.

## Testing

**Unit tests:** yes — role menu/copy contracts, status mapping, callback/access validation helpers if added.

**Integration tests:** yes — fake Google Sheets + temporary SQLite service tests for own-team participant list, manual report draft flow, step selection, duplicate guard, deadline guard, dropped participant guard, final weekly report rows, and admin-only error routing.

**E2E tests:** no for this local feature draft. Live Telegram callback handling and production bot smoke should be deferred to deployment/post-deploy verification.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|------|-----------------|
| 1. Captain-focused tests | `.venv/bin/python -m pytest tests/test_captain_* -q` | Captain can list own team and submit valid manual report; forbidden selections are rejected |
| 2. Weekly report regressions | `.venv/bin/python -m pytest tests/test_weekly_report_* -q` | Existing participant weekly report behavior still passes |
| 3. Boundary/security regressions | `.venv/bin/python -m pytest tests/test_participant_boundaries.py tests/test_boundaries.py -q` | Role boundaries and forbidden dependencies remain safe |
| 4. Full suite | `.venv/bin/python -m pytest -q` | All local tests pass |

### User verifies

- После будущего deploy/smoke на тестовом Telegram-боте: зайти как капитан, открыть команду, выбрать участника своей команды, отправить ручной weekly report до дедлайна, проверить строку Google Sheets с `submitted_by_role = captain`.
- Проверить, что капитан не видит участников чужой команды и не может отправить отчет после дедлайна.
