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

# User Spec: voice-processing

## What we're building
Добавляем обработку голосовых сообщений в существующие Telegram-флоу еженедельного отчета, инсайта и будущего капитанского ручного отчета. Пользователь сможет отправить голосовое до 10 минут, бот сохранит аудио локально, расшифрует его, добавит расшифровку в текущий черновик и сохранит итоговые бизнес-данные в Google Sheets при нажатии `✅ Готово`.

Фича не создает отдельный пользовательский раздел меню. Голосовые сообщения являются альтернативой текстовым сообщениям внутри уже начатого draft-флоу.

## Why
Участникам и капитанам проще быстро надиктовать отчет или инсайт, чем писать длинный текст в Telegram. При этом отчеты, инсайты и будущие PDF/Telegram-отчеты должны опираться на текстовую расшифровку, а не на долгосрочное хранение оригинального аудио.

## How it should work
1. Участник или капитан находится в активном флоу, где уже разрешен ввод текста: еженедельный отчет, инсайт или капитанский ручной отчет.
2. Пользователь отправляет голосовое сообщение.
3. Бот проверяет длительность.
4. Если голосовое длиннее 10 минут, бот не скачивает и не сохраняет его, а отвечает: `Голосовое длиннее 10 минут. Отправь, пожалуйста, более короткое голосовое или текст.`
5. Если голосовое до 10 минут включительно, бот скачивает файл из Telegram и сохраняет его в локальный непубличный путь `data/audio/{year}/week_{week_number}/{team_name}/{participant_id}/`.
6. Бот отправляет аудио в transcription boundary, получает текст и добавляет расшифровку в текущий draft в порядке сообщений.
7. Бот отвечает: `Голосовое принято и расшифровано.`
8. Когда пользователь нажимает `✅ Готово`, итоговый weekly report или insight сохраняется в Google Sheets с текстом расшифровки и локальным путем к аудио.
9. После успешного финального сохранения технический draft очищается по правилам соответствующего флоу; финальные бизнес-факты остаются в Google Sheets.
10. Если расшифровка или сохранение аудио падает, бот сообщает пользователю, что нужно повторить голосовое или написать текстом, уведомляет admin error chat и не теряет уже собранный draft.

## Acceptance Criteria
- [ ] Голосовое сообщение до 10 минут включительно принимается только внутри активного draft-флоу, где разрешен ввод отчета или инсайта.
- [ ] Голосовое сообщение длиннее 10 минут отклоняется утвержденным русским текстом, не сохраняется локально и не добавляется в draft.
- [ ] Принятое аудио сохраняется только в локальный непубличный путь под `data/audio/{year}/week_{week_number}/{team_name}/{participant_id}/`; path traversal и публичные URL недопустимы.
- [ ] После успешной расшифровки draft получает ordered message с типом voice transcription так, чтобы порядок текстовых и голосовых фрагментов сохранялся.
- [ ] Для weekly report финальное сохранение пишет в Google Sheets `report_text`, `transcription_text`, `audio_file_path` и не нарушает существующие правила статуса, дедлайна, step selection и duplicate guard.
- [ ] Для insight финальное сохранение пишет в Google Sheets `insight_text`, `transcription_text`, `audio_file_path` и не влияет на weekly status/progress.
- [ ] Если пользователь отправляет несколько текстовых и голосовых сообщений, итоговый текст собирается в исходном порядке.
- [ ] При ошибке скачивания, локального сохранения или транскрибации пользователь получает понятное сообщение с предложением повторить голосовое или отправить текст.
- [ ] При ошибке voice processing техническая ошибка уходит только через error bot/admin error chat; участникам, капитанам, трекерам и Александру Ситникову технические детали не отправляются.
- [ ] При ошибке voice processing существующий draft не очищается и не превращается в финальный Google Sheets факт.
- [ ] Оригинальное аудио не логируется, не коммитится и не становится доступным по публичной ссылке.
- [ ] После удаления аудио по retention future job система должна продолжать показывать/использовать `transcription_text` и не пытаться открыть удаленный файл как существующий.
- [ ] Фича не добавляет web form, Docker, Redis, Celery, PostgreSQL, публичные audio URLs, отдельный аудиоархив или коучинговые рекомендации.

## Constraints
- MVP канал остается только Telegram.
- Лимит голосового сообщения: 10 минут, то есть 600 секунд.
- Google Sheets остается финальным business storage для отчетов и инсайтов.
- SQLite хранит только технический draft state, temporary attachments и transient transcription state.
- Audio files хранятся локально на VPS и не публикуются наружу.
- Audio retention: оригинальное аудио удаляется автоматически через 1 месяц после записи; transcription text остается в Google Sheets.
- Все дедлайны weekly report проверяются в `Asia/Yekaterinburg`; voice input не может обходить deadline protection.
- Consent и Telegram ID identification обязательны до доступа к voice-enabled флоу.
- Для `green` и `blue` weekly report по-прежнему обязательны selected planned step IDs.
- Secrets для transcription provider хранятся только в `.env` локально или GitHub Actions secrets в CI/CD; пользователь не должен отправлять secrets в чат.

## Risks
- **Risk 1:** В SQLite может остаться полный чувствительный текст голосовой расшифровки после финального сохранения. **Mitigation:** хранить transcription в draft только до успешного Google Sheets save и очищать draft state по уже принятому storage boundary.
- **Risk 2:** Ошибка транскрибации может привести к потере пользовательского ответа. **Mitigation:** draft не очищается при ошибке; пользователь получает retry/text fallback; admin получает техническую ошибку.
- **Risk 3:** Небезопасный путь файла может привести к path traversal или публичной утечке аудио. **Mitigation:** использовать существующий `StoragePathPolicy`, safe fragments и непубличный локальный root.
- **Risk 4:** Голосовое может случайно обойти weekly deadline или duplicate guards. **Mitigation:** voice processing только добавляет fragment в draft; финальные status-changing правила остаются в weekly report finalize service.
- **Risk 5:** Внешний transcription provider может быть недоступен или неправильно настроен. **Mitigation:** provider изолируется за boundary, ошибки маршрутизируются в admin error chat, локальные тесты используют fake transcriber без live secrets.

## Technical Decisions
- We decided to implement voice processing as an input capability inside existing draft flows because weekly report and insight flows already own final validation and Google Sheets writes.
- We decided to keep `MAX_VOICE_DURATION_SECONDS = 600` as the single MVP limit because approved docs define a 10-minute maximum.
- We decided to store original audio locally and store only file path plus transcription in Google Sheets because long-term business source is transcription text, not the audio file.
- We decided to preserve mixed text/voice message order through draft messages because final report/insight text must reflect the user's actual sequence.
- We decided not to expose audio through public links because PDF/Telegram reports should show transcription text and role-safe data only.
- We decided not to implement the final audio cleanup scheduler in this feature unless the tech spec explicitly scopes it, because this slice is about receiving, storing, transcribing, and attaching voice messages to drafts.

## Testing

**Unit tests:** always done, not up for discussion.

**Integration tests:** yes — нужны service-level тесты с fake Telegram file downloader, fake speech transcriber, temporary SQLite и fake Sheets gateway, потому что фича соединяет Telegram input, local file policy, draft repositories, transcription boundary и финальные save flows.

**E2E tests:** no for this draft — live Telegram download and real transcription provider require production-like credentials and are better covered later by pre-deploy/post-deploy smoke tasks with test bot and test sheets. В этом user-spec достаточно локальной проверки через fakes.

## How to Verify

### Agent verifies

| Step | Tool | Expected result |
|-----|-----------|-------------------|
| 1. Run focused voice tests | `.venv/bin/python -m pytest tests/test_voice_processing*.py -q` | Голосовые до 600 секунд принимаются, больше 600 секунд отклоняются, ошибки не очищают draft |
| 2. Run related flow regressions | `.venv/bin/python -m pytest tests/test_weekly_report_* tests/test_insight_* tests/test_storage_paths.py tests/test_sqlite_schema.py -q` | Weekly report, insight, path policy и SQLite schema остаются совместимыми |
| 3. Run full suite | `.venv/bin/python -m pytest -q` | Весь локальный набор тестов проходит |
| 4. Check no generated audio/secrets are staged | `git status --short` and `git diff --check` | В commit попадают только code/tests/docs/work artifacts, без audio files или secrets |

### User verifies
- На тестовом Telegram-боте после будущего deploy/smoke: начать weekly report, отправить короткое голосовое, увидеть подтверждение расшифровки, нажать `✅ Готово`, проверить строку Google Sheets с transcription и audio path.
- На тестовом Telegram-боте после будущего deploy/smoke: отправить голосовое длиннее 10 минут и убедиться, что бот просит короткое голосовое или текст, а Google Sheets не получает финальный факт.
