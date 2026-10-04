# Telegram Scenarios

## Purpose

This document describes MVP Telegram bot scenarios for "Трекер целей".

The bot is a digital interviewer, data collector, history keeper, reminder engine, and report sender.

It is not a coach, therapist, motivator, or advice engine.

## Notification bot connection for captains

An active captain opens the Notification bot in a private chat and sends
`/start`. The bot verifies the Telegram ID against active `TeamCaptains` rows
for the bound flow, records the private chat and first connection timestamp,
then replies:

`Бот уведомлений подключён. Сюда будут приходить сводки и отчёты вашей команды.`

Unknown, inactive, other-flow, and group-chat starts do not change business
data and receive a short administrator-contact message.

## Manual RUPOR Broadcast

1. One of exactly three configured operators sends text to RUPOR in a private chat.
2. RUPOR selects active consenting rows with `role = participant` and a valid Telegram ID.
3. RUPOR shows the exact text, recipient count, and `Отправить всем` / `Отмена` buttons.
4. Confirmation atomically claims the broadcast and starts a rate-limited background send through Main bot.
5. Successful recipients are not sent the same broadcast twice; one recipient failure does not stop others.
6. RUPOR sends the operator a delivered/error summary and removes the draft text from SQLite.
7. Unknown users and group chats cannot create or confirm broadcasts.

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
- Unknown users may self-register only during the active flow's registration window.
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

### New User During Registration Window

1. User sends `/start` between `registration_opens_at` and `registration_closes_at`.
2. Bot shows the project welcome and personal-data consent.
3. After consent, bot asks for first name and surname in separate steps.
4. Bot shows both values for confirmation and allows either value to be corrected.
5. Bot creates one participant record identified by `flow_id + telegram_id`.
6. Bot sends the successful registration message, then a separate project rules
   message in HTML mode, before any next onboarding prompt. This applies to both
   participants and captains. Reopening `/start` or confirming an already
   completed registration does not resend the rules.

The rules message preserves this approved user-facing copy:

```html
ПРАВИЛА ПРОЕКТА (читать внимательно):

<u>Цель и шаги</u> — это как маяк и компас. На этом пути будут всплывать сложности и иллюзии. Мы здесь, чтобы с ними разобраться, а не чтобы делать вид, что их нет. Даже если цель на 100% будет не достигнута, победой будет смерть иллюзий и твердая уверенность, что цель точно будет достигнута.

Реалистичность: Реальная картина — это 1 новое действие в неделю поверх вашей ежедневной рутины. Если у вас в списке больше 8 шагов, значит, это микро-шаги одного большого дела. Не пишите действия, которые займут у вас «всю неделю».

<u>Цена слова</u> — Вы должны определить для себя цену своего слова. Это та «плата», которую вы отдадите, если не выполните обещанный шаг. Цена должна быть такой, чтобы сделать действие было психологически и физически выгоднее, чем заплатить эту цену. Идеальная картина: цена слова никогда не платится, потому что ваше слово — закон.

Последствия: Участник, который не выполнил действие, не заплатил цену слова и после этого не взломал свою иллюзию (не разобрался, что его остановило) — исключается из проекта. Беспощадно.
```

If registration completes after the ordinary goal setup deadline, the same Main Bot
continues in late-onboarding mode:

1. Show the successful registration message.
2. Send the project rules message above.
3. Collect and confirm the goal.
4. Collect exactly eight steps, each with an essence and achievement metric.
5. Ask for the participant's word price in rubles and save the numeric answer.
6. If a working week is active, request the current-week focus.

This exception lasts only through `registration_closes_at` and applies only to a
participant whose `onboarding_completed_at` is later than `goal_setup_end_date`.
It does not reopen the ordinary goal or step setup windows for existing participants.

Before the deadline, repeated `/start` resumes an unfinished registration draft or opens the menu for an already registered participant; it never creates a duplicate.

### New User After Registration Window

Message:

```text
Данный поток уже набран
```

This rejection applies when the Telegram ID has no participant record for the active flow. Existing registered participants continue normally; an unfinished registration draft does not reserve a place after the deadline.

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
- `Цена слова участников`
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

If no active goal exists, the same button starts goal creation:

1. Enter a short goal title.
2. Describe the concrete result.
3. Enter the measurable value/amount.
4. Enter the unit or currency.
5. Describe the achievement condition.
6. Review and confirm the complete goal.

The draft is technical state in SQLite. Only the confirmed active goal is appended to the
current flow's `Goals` tab. A participant cannot create a second active goal.

Editing a confirmed goal is not available in MVP.

## View Planned Steps

Trigger:
- `📍 Мои шаги`

Bot shows:
- progress percent
- word price in rubles from `WordPrices`, scoped by `flow_id + participant_id`
- all planned steps with visual status
- current weekly focus marker after the focused step number and before the title
- current progress percent

Participants create exactly eight initial steps during ordinary setup or their
authorized late-onboarding window. Adding further steps after that initial set is
not available in MVP.

Example:

```text
Прогресс: 33%
Цена слова: 5 000 ₽

🟩 Шаг 1. Найти клиента
⬜ Шаг 4. 🎯 Провести встречу
⬜ Шаг 5. Подписать договор
```

Step description is shown under the title as a native expandable Telegram blockquote,
the same way full insight text is displayed. It must not use spoiler blur.

If the word price has not been declared, show `Цена слова: не указана`.
Viewing steps does not modify the saved amount or start a new price interview.

Buttons:
- `Шаг {number}. {step_title} - Отчитаться` for open steps
- `Шаг {number}. {step_title} - Редактировать отчёт` for closed steps

These report-action buttons are shown only during an open working week. During
goal and steps setup, participants can view expandable step descriptions but do
not see report buttons. A stale report button from an older message returns the
first working-week opening date instead of claiming that a deadline has passed.

## Word Price During Initial Setup

After the initial eight steps have been confirmed and saved, ask:

```text
Какова твоя цена слова, если ты не выполнишь шаг за неделю?
Введи целое число рублей больше нуля, например: 5000.
```

This question is part of both ordinary setup and late onboarding and precedes
any current-week focus question. The amount belongs to the participant in the
current flow and is separate from the goal value.

For empty, nonnumeric, zero, negative, or fractional input, keep the question
active and reply:

```text
Введи целое число рублей больше нуля, например: 5000.
```

Save the accepted positive integer answer in `WordPrices`, linked by
`flow_id + participant_id`, before continuing. Do not create a duplicate row
when the same onboarding step is retried.

`/start` and `/menu` resume a pending price question after a restart. Old step
edit/cancel buttons keep this question active and do not recreate the saved plan.
A Google Sheets failure leaves the question active for a retry. A saved price
is not overwritten by a retry with a different value.

After saving, reply `Цена слова сохранена: {amount} ₽.` and request the weekly
focus if a working week is open. Otherwise, retain the normal menu entry points.
Participants who completed onboarding before this question was introduced are
not automatically asked to backfill a price just by opening their normal menu.

## Weekly Focus Flow

At the beginning of each week, if participant has open planned steps and no focus for the current week, bot asks:

```text
Неделя {week_number}: с {dd.mm.yyyy} по {dd.mm.yyyy}.

Выбери обязательный фокус недели.
```

Buttons:
- `⬜ Шаг {number}: {step}`

After selection:

```text
Фокус недели {week_number} (с {dd.mm.yyyy} по {dd.mm.yyyy}) сохранён: Шаг {number}
```

Rules:
- focus is mandatory
- focus can be selected only from open steps
- focus cannot be changed inside the same week
- closing the focused step does not require selecting a new focus
- focus does not prevent reporting another step in the same week

Every Monday at 21:00 Asia/Yekaterinburg, the notification bot sends each
captain an own-team summary:

```text
Фокусы команды «{team_name}» на {week_number}-ю неделю.

Выбрали приоритетный шаг: {selected_count} из {active_count} ({selected_percent}%).
✅ {participant_name} — «{step_title}»

Не выбрали: {missing_count} из {active_count} ({missing_percent}%).
❌ {participant_name}
```

This operational summary is captain-only. It is not sent to trackers, the
administrator, or Alexander Sitnikov.

## Captain Team Word Prices

Trigger: `Цена слова участников` in the captain menu.

The bot verifies a private chat, captain role, consent, active status, and an
active captain assignment to the team. It lists active consenting participants
with roles `participant` or `captain` from that same team and flow, sorted by
name. Word prices are joined by `flow_id + participant_id`.

Example:

```text
Цена слова участников

Анна Иванова — 5 000 ₽

Борис Петров — не указана
```

Missing declarations are shown as `не указана`; do not substitute zero. The
response is plain text and does not change amounts or participant data. Long
lists are split at participant boundaries with the continuation heading
`Цена слова участников — продолжение`. Other teams and flows are excluded.

## Captain Team Progress

Captain menu button:

```text
📊 Прогресс команды
```

The response is calculated from current Google Sheets data on every press and
contains only active consenting participants from the captain's own team:

```text
Прогресс команды на текущий момент

{participant_name}
Цель: {goal_symbol}
Шаги: {steps_symbol} {configured_steps} из 8
Фокус недели: {focus_step_or_state}
Выполнено: {closed_steps} из 8 — {progress_percent}%
{eight_cell_progress_bar}
```

## Captain Team Goals

Captain menu button:

```text
🎯 Цели команды
```

The bot shows one participant-selection button per active consenting member of
the captain's own team. Selecting a participant returns the active goal title,
description, value, permission condition, and permission metric. Both the list
and goal callback revalidate the active captain, exact active Teams assignment,
flow, team, participant status, consent, and private chat.

## Captain Team Steps

Captain menu button:

```text
📍 Шаги команды
```

The bot shows a paginated participant-selection list containing only active
consenting members of the captain's own team. Selecting a participant returns
the numbered planned steps of that participant's active goal in number order.
Open steps use `⬜`; closed steps use `🟩`. Both the list and detail callback
repeat the same captain, active Teams assignment, flow, team, participant,
consent, and private-chat authorization checks used by team goals.

## View Progress

Trigger:
- `📊 Мой прогресс`

Bot shows:
- goal setup status: `🟩` when an active goal exists, `⬜` while the setup deadline is open, `⬛` after a missed deadline
- planned-steps setup status: `🟩` when all eight numbered steps are filled, `⬜` while the setup deadline is open, `⬛` after a missed deadline
- progress percent
- main 8-cell planned-step progress bar
- weekly status history separately if useful
- current week status if available

The progress view remains available when the goal or planned steps are missing so
that the participant can see the corresponding setup status. Setup deadlines are
read from the bound active flow (`goal_setup_end_date` and
`steps_setup_end_date`) and are inclusive through the configured date.

## Step Report Flow

## Planned Steps Setup

Trigger:
- `📍 Мои шаги` when the active goal exists and no confirmed eight-step plan exists.

The bot collects exactly eight steps sequentially. For every step it asks first
for the concrete essence and then for the measurable completion metric. The
draft is stored in SQLite, can be resumed, and is written to `PlannedSteps` only
after the participant reviews all eight pairs and presses `✅ Подтвердить 8 шагов`.
Before confirmation, any numbered step can be rewritten. Empty descriptions or
metrics and answers over their configured limits are rejected.

After confirmation the regular `📍 Мои шаги` view shows the essence and metric
for each step. The plan is not editable after weekly focus/report activity starts.

### Start

Flow can start from:
- `Шаг {number}. {step_title} - Отчитаться` button on an open planned step
- Sunday 18:00 check-in
- reminder button if implemented

Bot shows selected step:

```text
Шаг {number}. {step_title}

Суть: {step_description}

Метрика: {step_metric}

Как выполнена метрика этого шага?
```

Buttons:
- `✅ Выполнена полностью`
- `🟦 Выполнена частично`
- `🟥 Не выполнена`

After the choice, the bot asks for the factual metric result. The participant
sends text/voice and confirms it with `✅ Отчёт готов`.

On save:
- save report to Google Sheets
- full completion saves `green` / `🟩`, a `closed` relation and closes the step;
- partial completion saves `blue` / `🟦`, a `partial` relation and keeps the step reportable;
- non-completion saves `red` / `🟥`, a `mentioned` relation and keeps the step open;
- save `metric_status` and the factual `metric_result_text` in the relation;
- clear SQLite draft

Confirmation:

```text
Принято. Победа недели сохранена.
```

### Edit Step Report

Trigger:
- `Шаг {number}. {step_title} - Редактировать отчёт` button on a closed step

Bot asks:

```text
Отправь новый текст отчёта по этому шагу.
```

Button:
- `✅ Отчёт готов`

On save:
- update existing report text
- update report `updated_at`
- do not change step `closed_at`
- do not change step `closed_week_number`
- do not change report `submitted_at`

Confirmation:

```text
Отчёт по шагу обновлён.
```

### No Answer

If participant does not submit any step report before Sunday 23:59 Yekaterinburg time:
- system creates or records status `gray` / `⬛`
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

Scheduled messages are selected from the active flow's materialized `FlowSchedule`. The table shows the exact date, calculated weekday, week number, week position, local time, role, and message for every event. The examples below form the default weekly template. Administrators may adjust a planned flow's schedule, enabled state, and Russian message text without changing recipient permissions or system behavior.

### Monday 10:00

If the participant has open planned steps and no focus for the current week, bot sends the weekly focus prompt with step selection buttons.
Otherwise bot sends:

```text
Новая неделя началась.

Проверь свои шаги и запланируй победу недели.
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

Если отчёт не будет отправлен до 23:59 по Екатеринбургу, неделя будет отмечена как ⬛ нет отчёта в срок.
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
