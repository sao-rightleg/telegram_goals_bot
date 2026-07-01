# Telegram Scenarios

## Purpose

This document describes MVP Telegram bot scenarios for "Трекер целей".

The bot is a digital interviewer, data collector, history keeper, reminder engine, and report sender.

It is not a coach, therapist, motivator, or advice engine.

## Tone of Voice

User-facing messages are in Russian.

Tone:
- short
- clear
- calm
- practical
- respectful

Avoid:
- long lectures
- moralizing
- therapy language
- excessive emojis
- fake enthusiasm
- unsolicited advice

## Common Rules

- Identify user by Telegram ID.
- If user is unknown, show approved not-in-base message and notify admin.
- Require consent before continuing.
- Generate menu by role.
- Captains see only own team.
- Participants see only own data.
- Insights do not change weekly status.
- Late reports after Sunday 23:59 Yekaterinburg time do not change status.
- No yellow late status.
- Draft state is stored in SQLite.
- Final business facts are stored in Google Sheets.

## First Start

### Known User With Consent

1. User sends `/start`.
2. Bot finds Telegram ID in Google Sheets.
3. Bot sees consent is already given.
4. Bot shows role-based menu.

### Known User Without Consent

1. User sends `/start`.
2. Bot finds Telegram ID in Google Sheets.
3. Bot shows consent text:

```text
Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору и Александру Ситникову в рамках челленджа.
```

Button:
- `✅ Согласен`

After click:
- save `consent_given`
- save `consent_given_at`
- show role-based menu

If user does not consent, bot must not continue.

### Unknown User

Message:

```text
Извините, вас нет в базе участников. Свяжитесь со своим капитаном.
```

Admin notification:
- error type: unknown Telegram user
- Telegram ID
- username if available
- date/time

## Participant Menu

Buttons:
- `🎯 Моя цель`
- `📍 Мои шаги`
- `📊 Мой прогресс`
- `💡 Мои инсайты`

## Captain Menu

Captain is also a participant.

Buttons:
- `🎯 Моя цель`
- `📍 Мои шаги`
- `📊 Мой прогресс`
- `💡 Мои инсайты`
- `👥 Моя команда`
- `➕ Внести отчёт за участника`
- `📄 Отчёт команды`

## View Goal

Trigger:
- `🎯 Моя цель`

Bot shows:
- goal title
- goal description
- goal value
- permission condition

No editing in MVP.

## View Planned Steps

Trigger:
- `📍 Мои шаги`

Bot shows:
- open planned steps
- closed planned steps if useful
- current progress percent

No participant-created steps in MVP.

## View Progress

Trigger:
- `📊 Мой прогресс`

Bot shows:
- progress percent
- main 6-cell planned-step progress bar
- weekly status history separately if useful
- current week status if available

## Weekly Report Flow

### Start

Flow can start from:
- user action
- Sunday 18:00 check-in
- reminder button if implemented

Bot shows remaining planned steps:

```text
На этой неделе у тебя остались незакрытые шаги:

1. {step}
2. {step}
3. {step}

Выбери статус недели.
```

Buttons:
- `🟩 Победа есть`
- `🟦 Частично`
- `🟥 Победы нет`

### Green Status

If user selects `🟩 Победа есть`:

Bot asks:

```text
Что именно ты сделал?
```

Bot requires selecting one or more planned steps that were completed.

If no step is selected, bot must not save `🟩` status.

Then bot says:

```text
Можешь отправить одно или несколько сообщений. Когда закончишь — нажми ✅ Готово.
```

Button:
- `✅ Готово`

On save:
- save weekly report to Google Sheets
- save status `green` / `🟩`
- save score `1`
- save selected step relations as `closed`
- close selected planned steps
- clear SQLite draft

Confirmation:

```text
Принято. Победа недели сохранена.
```

### Blue Status

If user selects `🟦 Частично`:

Bot requires selecting one or more planned steps with partial progress.

If no step is selected, bot must not save `🟦` status.

Bot asks:

```text
Что получилось сделать частично?
```

Then:

```text
Что не хватило до полноценной победы?
```

Then:

```text
Можешь отправить одно или несколько сообщений. Когда закончишь — нажми ✅ Готово.
```

On save:
- save weekly report to Google Sheets
- save status `blue` / `🟦`
- save score `0.5`
- save selected step relations as `partial`
- clear SQLite draft

Confirmation:

```text
Принято. Частичная победа сохранена.
```

### Red Status

If user selects `🟥 Победы нет`:

Bot asks:

```text
Что помешало сделать победу недели?
```

Optional second prompt:

```text
Что понял по итогам недели?
```

This answer is not an insight unless participant explicitly adds it as insight.

On save:
- save weekly report to Google Sheets
- save status `red` / `🟥`
- save score `0`
- clear SQLite draft

Confirmation:

```text
Принято. Отчёт за неделю сохранён.
```

### No Answer

If participant does not submit weekly report before Sunday 23:59 Yekaterinburg time:
- system creates or records status `gray` / `⬜`
- score is `0`
- no yellow late status is created

After Sunday 23:59, bot may save late report text if implemented, but it must not change the closed week's status.

## Multiple Messages

While user is in report or insight flow:
- collect text messages
- collect voice messages
- transcribe voice messages
- preserve message order
- store draft in SQLite

Final save happens only after `✅ Готово`.

If user presses `✅ Готово` without content:
- ask for text or voice report before saving
- do not create empty final report unless admin explicitly approves this behavior later

## Voice Message Flow

If voice is under or equal to 10 minutes:
- download audio
- store locally under `data/audio/{year}/week_{week_number}/{team_name}/{participant_id}/`
- transcribe
- attach transcription to draft

Confirmation:

```text
Голосовое принято и расшифровано.
```

If voice is over 10 minutes:

```text
Голосовое длиннее 10 минут. Отправь, пожалуйста, более короткое голосовое или текст.
```

If transcription fails:

```text
Не удалось распознать голосовое. Надиктуй ещё раз или напиши текстом для верности.
```

Also notify admin through error bot.

## Insight Flow

Trigger:
- `💡 Мои инсайты`

Options:
- `➕ Добавить инсайт`
- `📜 Посмотреть инсайты`

When adding insight, bot asks:

```text
К чему относится инсайт?
```

Buttons:
- `Текущая неделя`
- `Прошлая неделя`
- `К цели в целом`

Then:

```text
Запиши инсайт текстом или голосом.
```

After save:

```text
Инсайт сохранён.
```

Rules:
- insight does not count as victory
- insight does not change weekly status
- insight is saved separately from weekly report

## Captain Team View

Trigger:
- `👥 Моя команда`

Bot shows:
- team name
- participant list
- current week status
- progress percent

Keep it short and limited to captain's own team.

## Captain Manual Report

Trigger:
- `➕ Внести отчёт за участника`

Flow:
1. Bot lists only participants from captain's team.
2. Captain selects participant.
3. Bot shows current week.
4. Captain selects status:
   - `🟩 Победа есть`
   - `🟦 Частично`
   - `🟥 Победы нет`
5. For `🟩` or `🟦`, captain selects one or more related planned steps.
6. Captain sends text or voice report.
7. Captain presses `✅ Готово`.
8. Bot saves report if before deadline.

Captain cannot submit a report for a dropped participant.

If after deadline:

```text
Дедлайн недели уже прошёл. Отчёт не может изменить статус.
```

Saved data:
- participant id
- captain id
- team id
- week number
- status
- selected step ids for `🟩` or `🟦`
- report text
- transcription if voice
- audio file path if voice
- submitted by captain
- submitted at

## Reminders

### Monday 10:00

```text
Новая неделя началась.

У тебя остались незакрытые шаги:
{steps}

На этой неделе важно закрыть хотя бы один шаг.
```

### Wednesday 10:00

```text
Короткий чек-ап.

Как идёт движение по шагам на этой неделе?
```

### Sunday 18:00

```text
Финальный чек-ап недели.

Выбери статус недели и оставь короткий отчёт.
```

### Sunday 22:30

```text
Напоминание: отчёт за неделю ещё не отправлен.

Дедлайн сегодня в 23:59 по Екатеринбургу.
```

### Sunday 23:00

```text
Последнее напоминание.

Если отчёт не будет отправлен до 23:59 по Екатеринбургу, неделя будет отмечена как ⬜ нет ответа.
```

If weekly report already exists, do not send more reminders that week.

## All Steps Completed

If all current planned steps are closed before challenge end:

```text
Все текущие шаги закрыты. Обратись к капитану или трекеру, чтобы определить следующий маршрут.
```

Rules:
- bot does not automatically mark final goal as achieved
- if goal is achieved, tracker or admin fixes goal achievement
- if goal is not achieved, participant prepares additional steps with captain/tracker
- admin adds new/additional steps in Google Sheets
- until new steps are added, bot must not require closing a non-existent step

## Broken State Recovery

If SQLite state is invalid:
- log error
- notify admin if needed
- clear unsafe state
- return user to menu

User message:

```text
Состояние диалога сбилось. Вернул тебя в меню.
```

## Product Decisions

Resolved product decisions are recorded in `docs/02_open_questions.md`.

Tracker/admin/Sitnikov interactive menus are not defined in MVP scenarios yet; current MVP covers participant and captain user scenarios plus passive report delivery.
