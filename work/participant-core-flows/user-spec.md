---
created: 2026-07-02
status: draft
type: feature
size: M
---

# User Spec: participant-core-flows

## What we're building

Реализуем первый пользовательский слой Telegram-бота после foundation: `/start`, идентификацию пользователя по Telegram ID, обработку неизвестного пользователя, consent flow, role-aware меню и read-only просмотры для цели, шагов и прогресса участника.

Фича должна дать известному участнику понятный вход в бота и базовую навигацию по своим данным, но не должна пока реализовывать недельные отчёты, инсайты, голосовые сообщения, captain manual report, scheduler, PDF или production deploy.

## Why

Foundation уже создал конфигурацию, SQLite schema, scheduler constants, storage paths и integration boundaries, но пользователь всё ещё не может открыть бота и увидеть свои данные.

Эта фича создаёт минимальный безопасный пользовательский контур: бот понимает, кто пишет, требует consent до продолжения, показывает меню по роли и отдаёт участнику его цель, шаги и прогресс из Google Sheets как business source of truth.

## How it should work

1. Пользователь отправляет `/start`.
2. Бот ищет Telegram ID в Google Sheets через boundary/repository слой.
3. Если Telegram ID не найден:
   - пользователь получает текст: `Извините, вас нет в базе участников. Свяжитесь со своим капитаном.`;
   - error bot получает техническое уведомление для admin error chat с Telegram ID, username если есть, и временем события;
   - пользовательский flow не продолжается.
4. Если пользователь найден, но consent ещё не дан:
   - бот показывает текст consent: `Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору и Александру Ситникову в рамках челленджа.`;
   - показывает кнопку `✅ Согласен`;
   - до согласия не показывает меню и не отдаёт данные участника.
5. После нажатия `✅ Согласен`:
   - consent сохраняется в Google Sheets (`consent_given`, `consent_given_at`);
   - бот показывает role-aware меню.
6. Если пользователь найден и consent уже есть:
   - бот сразу показывает role-aware меню.
7. Participant menu содержит:
   - `🎯 Моя цель`
   - `📍 Мои шаги`
   - `📊 Мой прогресс`
   - `💡 Мои инсайты`
8. Captain menu содержит participant menu плюс:
   - `👥 Моя команда`
   - `➕ Внести отчёт за участника`
   - `📄 Отчёт команды`
9. В рамках этой фичи кнопка `💡 Мои инсайты` может быть показана в меню, но полноценный insight flow не реализуется. Если пользователь нажмёт её до отдельной insight-фичи, бот должен ответить коротким сообщением, что раздел будет доступен позже, без записи business facts.
10. При нажатии `🎯 Моя цель` бот показывает:
    - название цели;
    - описание цели;
    - ценность цели;
    - условие разрешения.
11. При нажатии `📍 Мои шаги` бот показывает:
    - открытые planned steps;
    - закрытые planned steps, если они есть;
    - текущий процент прогресса.
12. При нажатии `📊 Мой прогресс` бот показывает:
    - основной 6-cell progress bar по шагам;
    - процент прогресса;
    - weekly status history как вторичную информацию, если эти данные уже доступны из Google Sheets.
13. Если в Google Sheets у известного пользователя не хватает критичных данных для view (`team_id`, активная цель, planned steps), бот не падает:
    - пользователь получает короткое нейтральное сообщение о том, что данные пока не заполнены;
    - admin error chat получает техническое уведомление с типом missing required data.

## Acceptance Criteria

- [ ] `/start` идентифицирует пользователя по Telegram ID через Google Sheets boundary, а не через SQLite.
- [ ] Неизвестный Telegram ID получает утверждённое сообщение “вас нет в базе участников”.
- [ ] Unknown-user event отправляется только в admin error chat через error bot boundary.
- [ ] Известный пользователь без consent видит утверждённый consent text и кнопку `✅ Согласен`.
- [ ] До consent бот не показывает меню и не отдаёт цель/шаги/прогресс.
- [ ] После consent бот сохраняет `consent_given` и `consent_given_at` в Google Sheets boundary.
- [ ] Пользователь с уже сохранённым consent сразу получает role-aware menu.
- [ ] Participant menu содержит только participant-кнопки из утверждённых сценариев.
- [ ] Captain получает participant-кнопки плюс captain-кнопки из утверждённых сценариев.
- [ ] Participant не видит данные других участников.
- [ ] View Goal показывает только данные цели текущего участника.
- [ ] View Planned Steps показывает planned steps текущего участника и не позволяет создавать новые шаги.
- [ ] View Progress показывает 6-cell progress bar и процент прогресса по planned steps.
- [ ] Missing required participant/goal/step data не приводит к crash и отправляет admin error notification без секретов.
- [ ] SQLite используется только для technical dialog/menu/consent state, если состояние нужно сохранить между сообщениями.
- [ ] Финальные business facts остаются в Google Sheets; SQLite не становится business storage.
- [ ] Unit/integration tests проходят без production Telegram token и Google credentials.
- [ ] Фича не реализует weekly report submission, insight submission, voice processing, captain manual report, scheduler, PDF generation или production deploy.

## Constraints

- User-facing Telegram messages must be in Russian.
- Tone must stay short, clear, calm, practical, and respectful.
- Do not ask the user to send secrets in chat.
- Do not commit `.env`, Google credentials, audio/PDF files, SQLite DB files, or backups.
- Google Sheets remains the business source of truth.
- SQLite stores only technical state.
- Main bot handles participant/captain user interaction.
- Error bot handles technical errors only.
- Notification bot is not used for ordinary menu/view replies in this feature.
- Production deploy is out of scope.
- Docker, PostgreSQL, Redis, Celery, Kubernetes, web admin panel, and web form are out of MVP.

## Risks

- **Risk 1:** фича может разрастись в weekly reports или insight flow. **Mitigation:** оставить отчёты, инсайты, голос и captain manual report отдельными фичами; в этой фиче только вход, consent, меню и read-only views.
- **Risk 2:** Telegram handlers могут начать напрямую читать Google Sheets или писать SQLite. **Mitigation:** держать handlers тонкими и выносить orchestration в services/repositories.
- **Risk 3:** неизвестный пользователь или missing sheet data могут раскрыть лишние персональные данные в error notification. **Mitigation:** отправлять admin error с техническим контекстом и ID, без токенов и без лишнего текста отчётов/целей.
- **Risk 4:** progress display может смешать weekly status history и основной progress bar. **Mitigation:** считать основной progress только по planned steps и показывать weekly history как вторичную информацию.

## Technical Decisions

- We decided to scope this feature to `/start`, identity, consent, menu, and read-only participant views because these flows are prerequisites for weekly reports, insights, voice, and captain features.
- We decided to use Google Sheets as the source for participant, consent, goal, planned-step, and progress business data because this is the approved MVP storage boundary.
- We decided to use SQLite only for technical dialog/menu state because SQLite must not become business storage.
- We decided to route unknown-user and missing-data errors through the existing error bot boundary because technical errors must not go to participants, captains, trackers, or Alexander Sitnikov.
- We decided not to include production deploy in this feature because deployment is a separate MVP phase and requires explicit approval.

## Testing

**Unit tests:** always done, not up for discussion.

**Integration tests:** yes — фича связывает Telegram scenario orchestration, Google Sheets fake/repository, notification routing и SQLite technical state; одних unit tests недостаточно.

**E2E tests:** no for this user-spec by default — production Telegram bot and live Google Sheets are not required. If tech-spec introduces a real Telegram SDK adapter in this feature, tech-spec must decide whether a local adapter-level E2E/smoke test is needed.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| Run full test suite | `python -m pytest -v` | All tests pass without production secrets |
| Verify known user with consent | pytest integration test with fake Sheets and fake bot | `/start` returns role-aware menu |
| Verify known user without consent | pytest integration test with fake Sheets and fake bot | bot shows consent text and does not show menu before consent |
| Verify consent accept | pytest integration test | `consent_given` and `consent_given_at` are written through Sheets boundary and menu is shown |
| Verify unknown user | pytest integration test | approved message is sent to user and technical error is routed only through error bot |
| Verify goal/steps/progress views | pytest integration tests with fake Sheets data | only current participant data is shown |
| Verify missing data handling | pytest integration test | user receives safe message and admin error is routed without secrets |
| Verify out-of-scope boundaries | static/test checks | no weekly report, voice, PDF, scheduler, deploy, Docker/PostgreSQL/Redis/Celery/Kubernetes added |

### User verifies

- Проверить `user-spec.md` и подтвердить, что scope не включает недельные отчёты, инсайты, голос, captain manual report и deploy.
- Проверить русские тексты `/start`, unknown user, consent, menu и missing data на соответствие тону проекта.
