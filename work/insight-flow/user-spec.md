---
created: 2026-07-02
status: approved
type: feature
size: M
---

# User Spec: insight-flow

## What we're building

Реализуем personal insight flow для участника: раздел `💡 Мои инсайты`, добавление текстового инсайта за текущую неделю, короткий заголовок инсайта, сохранение финального Insight в Google Sheets, просмотр своих инсайтов списком, пагинацию и открытие полного текста через `читать целиком`.

Фича должна дать участнику место для фиксации важных наблюдений отдельно от недельного отчёта и прогресса. Она не должна пока реализовывать реальную обработку голосовых, team insight view для капитана, отчёты, PDF, scheduler, live Telegram SDK, live Google API adapter или production deploy.

## Why

В MVP инсайты нужны как отдельный слой наблюдений: участник может понять что-то важное даже без победы недели, но такой инсайт не должен менять статус, score, planned steps или процент прогресса.

`participant-core-flows` уже показывает кнопку `💡 Мои инсайты`, но она пока inert. Эта фича превращает её в рабочий personal flow и сохраняет инсайты как business facts в Google Sheets, чтобы позже они могли попадать в weekly summary и отчёты.

## How it should work

1. Участник нажимает `💡 Мои инсайты`.
2. Бот показывает действия:
   - `➕ Добавить инсайт`
   - `📜 Посмотреть инсайты`
3. Капитан в рамках этой фичи использует тот же personal insight flow только для своих инсайтов. Инсайты участников команды капитан в этой фиче не видит.
4. Если пользователь неизвестен, бот использует утверждённый unknown-user flow:
   - пользователь получает `Извините, вас нет в базе участников. Свяжитесь со своим капитаном.`;
   - admin error chat получает technical notification.
5. Если пользователь найден, но consent ещё не дан, бот показывает утверждённый consent text и не отдаёт данные инсайтов.
6. При `➕ Добавить инсайт` бот создаёт SQLite draft для текущего участника.
7. Добавление инсайта в этой фиче всегда относится к текущей challenge week.
   - Бот сохраняет `week_number` по утверждённому календарю `Asia/Yekaterinburg`.
   - Бот сохраняет `insight_scope = current_week`.
   - Бот сохраняет отдельный `insight_date` для отображения даты инсайта в списках и отчётах.
   - `Прошлая неделя` и `К цели в целом` не используются в add flow этой фичи.
8. Если у участника нет активной цели в Google Sheets, инсайт не сохраняется. Бот отвечает:

```text
Прости, у тебя не зафиксировано активной цели, обратись к капитану
```

9. Бот просит отправить инсайт текстом.
10. Реальная обработка voice messages не входит в эту фичу. Если участник отправляет voice message до реализации общей `voice-processing` фичи, бот должен ответить коротко, что голосовые инсайты будут доступны позже, и попросить отправить текст.
11. Участник может отправить одно или несколько текстовых сообщений. SQLite draft сохраняет порядок сообщений.
12. Если участник нажимает `✅ Готово` без текста, финальный Insight не создаётся. Бот сообщает, что ничего не получил в качестве инсайта, и просит отправить текст ещё раз.

```text
Я не получил текст инсайта. Отправь инсайт текстом и нажми ✅ Готово.
```

13. После текста бот спрашивает:

```text
Как кратко озаглавить твой инсайт?
```

14. Участник может ввести заголовок или нажать `Пропустить`.
15. Заголовок ограничен 120 символами. Если заголовок длиннее, бот просит сократить.
16. Если заголовок пропущен, бот использует первые 80-100 символов текста как fallback title.
17. После успешного сохранения бот отвечает:

```text
Инсайт сохранён.
```

18. После сохранения бот очищает SQLite draft и возвращает обычное role-aware menu.
19. Если `✅ Готово` нажато повторно после сохранения, второй финальный Insight не создаётся. Бот отвечает:

```text
Инсайт уже сохранён.
```

20. Кнопка `Отмена` внутри add flow очищает SQLite draft и возвращает обычное role-aware menu без сохранения Insight.
21. При `📜 Посмотреть инсайты` бот показывает только инсайты текущего участника, newest-first.
22. Если инсайтов нет, бот отвечает:

```text
У тебя пока нет сохранённых инсайтов.
```

23. Список показывает последние 10 инсайтов. Если инсайтов больше, бот показывает пагинацию:
   - `← Раньше`
   - `Позже →`
24. Пагинация не должна уходить за доступные страницы.
25. Один insight item в списке показывает:
   - дату инсайта;
   - заголовок;
   - короткое preview текста или будущей расшифровки;
   - action `читать целиком`.
26. Preview заканчивается визуально как `...читать целиком`, но технически `читать целиком` должен быть Telegram callback/inline action по `insight_id`, а не публичная ссылка.
27. При нажатии `читать целиком` бот отправляет полный текст выбранного инсайта отдельным сообщением.
28. Full-text callback должен быть participant-scoped: участник не может получить чужой Insight по `insight_id`.
29. Если callback устарел или Insight не найден, бот отвечает:

```text
Инсайт не найден.
```

И отправляет technical notification в admin error chat.
30. Финальный Insight сохраняется в Google Sheets. SQLite хранит только temporary draft/dialog state.

## Acceptance Criteria

- [ ] `💡 Мои инсайты` перестаёт быть inert action и открывает personal insight menu.
- [ ] Insight menu содержит `➕ Добавить инсайт` и `📜 Посмотреть инсайты`.
- [ ] Unknown user получает утверждённый unknown-user message, а admin error chat получает technical notification.
- [ ] Пользователь без consent не может добавлять или смотреть инсайты.
- [ ] Капитан в этой фиче видит и добавляет только свои личные инсайты.
- [ ] Add flow создаёт SQLite draft для текущего участника и не пишет final business facts до сохранения.
- [ ] Add flow сохраняет инсайт только за текущую challenge week.
- [ ] Final Insight сохраняется с `insight_scope = current_week`.
- [ ] Final Insight содержит `insight_id`, `participant_id`, `goal_id`, `week_number`, `insight_scope`, `insight_title`, `insight_date`, `insight_text`, `created_by_id`, `created_by_role`, `created_at`.
- [ ] `Insights` schema получает новые поля `insight_title` и `insight_date`.
- [ ] Если у участника нет активной цели, Insight не сохраняется и пользователь получает `Прости, у тебя не зафиксировано активной цели, обратись к капитану`.
- [ ] Пустой draft / `✅ Готово` без текста не создаёт Insight.
- [ ] Несколько текстовых сообщений собираются в `insight_text` в правильном порядке.
- [ ] После текста бот просит короткий заголовок: `Как кратко озаглавить твой инсайт?`.
- [ ] Заголовок длиннее 120 символов не принимается, бот просит сократить.
- [ ] `Пропустить` создаёт fallback title из первых 80-100 символов текста.
- [ ] После успешного save бот отвечает `Инсайт сохранён.`, очищает draft и возвращает обычное role-aware menu.
- [ ] Повторное сохранение уже сохранённого draft не создаёт duplicate Insight и отвечает `Инсайт уже сохранён.`.
- [ ] `Отмена` очищает draft и возвращает обычное role-aware menu без записи Insight.
- [ ] `📜 Посмотреть инсайты` показывает только инсайты текущего участника.
- [ ] Empty list показывает `У тебя пока нет сохранённых инсайтов.`.
- [ ] List view показывает последние 10 инсайтов newest-first.
- [ ] Если инсайтов больше 10, pagination `← Раньше` / `Позже →` позволяет смотреть старые и новые страницы.
- [ ] Pagination не показывает несуществующие страницы и не падает на границах.
- [ ] Каждый truncated item имеет `читать целиком` callback для открытия полного текста.
- [ ] Full-text callback возвращает полный текст только если Insight принадлежит текущему участнику.
- [ ] Missing/stale full-text callback отвечает `Инсайт не найден.` и отправляет admin technical notification.
- [ ] Insight не создаёт WeeklyReport, WeeklyReportSteps, planned-step closure, weekly status, score, scheduler job, PDF или voice record.
- [ ] SQLite не становится business storage: финальные Insight facts живут только в Google Sheets boundary.
- [ ] Unit/integration tests проходят без production Telegram token, Google credentials, transcription provider, live Telegram messages или network.

## Constraints

- User-facing Telegram messages must be in Russian.
- Tone must stay short, clear, calm, practical, and respectful.
- Google Sheets remains the business source of truth for final Insights.
- SQLite stores only technical draft/dialog state.
- Primary identity is Telegram ID resolved through Google Sheets boundary.
- Consent is required before the participant can add or view insights.
- Main bot handles participant/captain interaction.
- Error bot handles technical errors only.
- Do not expose full insight text through public links.
- Do not expose another participant's insight via callback, pagination, logs, or error messages.
- Real voice transcription is out of scope for this feature and must be implemented later in shared `voice-processing`.
- Team insight access for captain is out of scope for this feature.
- Scheduler summaries, PDF reports, live Telegram SDK, live Google API adapter, deploy, push, and production actions are out of scope.
- No Docker, PostgreSQL, Redis, Celery, Kubernetes, web admin panel, or web form in MVP.

## Risks

- **Risk 1:** фича может разрастись в voice processing. **Mitigation:** в этой фиче только текстовые insights и compatibility with future voice drafts; реальную транскрибацию вынести в shared `voice-processing`.
- **Risk 2:** капитан может случайно получить доступ к инсайтам команды раньше отдельной captain/reporting фичи. **Mitigation:** все list/get операции scope by current participant_id; captain in this feature is treated as personal participant.
- **Risk 3:** `читать целиком` может раскрыть чужой Insight через guessed/stale `insight_id`. **Mitigation:** every callback resolves by both current participant_id and insight_id.
- **Risk 4:** Google Sheets schema может не совпасть с новым UX заголовков. **Mitigation:** явно добавить `insight_title` и `insight_date` в user-spec/tech-spec и manual user actions.
- **Risk 5:** список инсайтов может засорить чат при большом количестве записей. **Mitigation:** показывать latest 10 и использовать pagination.
- **Risk 6:** SQLite draft может стать источником финальных business facts. **Mitigation:** после save очищать draft, а финальные Insights писать только в Google Sheets.

## Technical Decisions

- We decided to add `insight_title` to `Insights` because the list view needs a stable user-facing title and hiding it inside `insight_text` would make reports and pagination fragile.
- We decided to add `insight_date` because `created_at` is technical save time, while reports and list views need a clear user-facing insight date.
- We decided to allow adding insights only for the current week in this feature because adding previous-week insights is not needed for the current challenge state.
- We decided to allow unlimited insights per week because insights are observations, not weekly status records.
- We decided to defer real voice processing because weekly reports and insights should share one audio/transcription mechanism.
- We decided to implement `читать целиком` as a participant-scoped callback by `insight_id`, not as a public URL, because full insight text is private.
- We decided to return to the ordinary role-aware menu after saving because the user is done with the add flow and should not be trapped in the insight submenu.
- We decided not to include production deploy in this feature because deployment requires explicit approval and must go through GitHub CI/CD.

## Testing

**Unit tests:** always done, not up for discussion.

**Integration tests:** yes — фича связывает participant identity/consent, Sheets fake, SQLite draft state, calendar week binding, pagination, participant-scoped callbacks и final Google Sheets writes.

**E2E tests:** no — live Telegram bot, live Google Sheets, voice provider and production deploy are out of scope for this user-spec.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| Run full test suite | `.venv/bin/python -m pytest -v` | All tests pass without production secrets |
| Verify insight menu | pytest service/copy test | `💡 Мои инсайты` returns add/list actions |
| Verify add text insight | pytest integration test with fake Sheets and temp SQLite | Insight row saved with participant_id, goal_id, week_number, insight_title, insight_date, insight_text |
| Verify missing active goal | pytest integration test | no Insight row is saved; user receives approved active-goal message |
| Verify empty draft | pytest integration test | `✅ Готово` without text creates no Insight and asks user to repeat |
| Verify title validation | pytest unit/service test | title over 120 chars is rejected; `Пропустить` uses fallback title |
| Verify cancel | pytest integration test | draft is cleared and no Insight row is saved |
| Verify duplicate finalization | pytest integration test | second `✅ Готово` creates no duplicate and returns `Инсайт уже сохранён.` |
| Verify personal list | pytest integration test | participant sees only own insights, latest 10 first |
| Verify pagination | pytest integration test | 16 insights are split into pages; older/newer navigation stays within bounds |
| Verify full text callback | pytest integration test | current participant can open own full text; cannot open another participant's insight |
| Verify stale callback | pytest integration test | missing insight returns `Инсайт не найден.` and routes admin technical notification |
| Verify storage boundary | static/test checks | final facts only in Sheets fake; SQLite contains only draft/dialog state |
| Verify out-of-scope boundaries | static/test checks | no real voice transcription, scheduler, PDF, deploy, live SDK, team insight view, WeeklyReport writes, planned-step closure, status or score changes |

### User verifies

- Проверить `user-spec.md` и подтвердить, что фича ограничена personal text insight flow.
- Проверить русские тексты: меню инсайтов, вопрос про заголовок, empty list, no active goal, save success, duplicate save, missing insight.
- Проверить, что решение “только текущая неделя” соответствует ожидаемому поведению для текущего запуска челленджа.
- До live use добавить в Google Sheets `Insights` новые колонки `insight_title` и `insight_date`.
