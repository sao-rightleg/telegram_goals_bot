# Requirements

## 1. Project summary

"Трекер целей" is an MVP Telegram bot for the challenge "Смерть иллюзий".

The bot collects weekly progress reports from participants, stores goals and planned steps, accepts voice and text answers, supports captains, generates Telegram and PDF reports, and notifies the admin about errors.

The system is not a coach and not a motivator.

The system is:
- digital interviewer
- data collector
- history keeper
- reminder engine
- report generator

## 2. MVP channel

The first MVP channel is Telegram.

Web form is not part of the first MVP, but the architecture must allow adding it later.

## 3. Storage

### 3.1 Business storage

Google Sheets is the main business database for MVP.

It stores:
- participants
- teams
- captains
- trackers
- goals
- planned steps
- weekly reports
- insights
- status data
- report data

### 3.2 Technical storage

SQLite on VPS is used for technical bot state.

It stores:
- active dialog state
- draft answers
- temporary message buffers
- current flow
- selected participant for captain manual report
- selected status
- scheduler jobs
- error log

### 3.3 Files

Audio files are stored locally on VPS.

PDF reports are generated and stored locally before sending.

## 4. Roles

## 4.1 Participant

Participant can:
- start bot
- give consent
- view goal
- view planned steps
- view progress
- submit weekly report
- submit insight
- send text answer
- send voice answer up to 10 minutes

Participant cannot:
- add new planned steps in MVP
- edit past weeks
- change past week status after deadline
- access other participants' data

## 4.2 Captain

Captain is also a participant.

Captain has additional responsibilities:
- receives notifications about silent participants in own team
- manually adds reports for participants in own team
- receives PDF report for own team

Captain cannot:
- add reports for other teams
- add reports after official deadline
- access reports outside own team

## 4.3 Tracker

Tracker supervises several teams.

Trackers:
- Ivan Larkin receives all male team reports
- Maria receives all female team reports

Tracker receives:
- team Telegram summaries
- PDF reports for assigned teams
- notifications about silent participants in assigned teams

## 4.4 Admin

Admin is Alexander.

Admin:
- manages Google Sheets
- receives all reports
- receives all errors
- has access to all data

## 4.5 Alexander Sitnikov

Alexander Sitnikov:
- receives all reports
- receives group comparison summaries
- can review the whole challenge picture

## 5. Consent

At first bot start, participant must give consent.

Consent text:

"Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору и Александру Ситникову в рамках челленджа."

If participant does not consent, bot must not continue.

Consent must be stored in Google Sheets.

## 6. Identification

Primary identification is Telegram ID.

If Telegram ID is not found in Google Sheets, bot replies:

"Извините, вас нет в базе участников. Свяжитесь со своим капитаном."

Unknown user event must be sent to admin error chat.

## 7. Goal model

Goal is a concrete desired object or result.

Goal is not simply money.

Goal fields:
- goal title
- goal description
- goal value amount
- goal value currency
- permission condition
- permission metric amount
- permission metric unit

Example:
- goal title: "Комплект мебели домой"
- goal description: "Кровать, стол, стулья"
- goal value amount: 100000
- goal value currency: RUB
- permission condition: "Заработать 300 000 ₽ в бизнесе за 2 месяца"
- permission metric amount: 300000
- permission metric unit: RUB

## 8. Planned steps

Each participant has predefined planned steps.

Steps are not tied to specific weeks.

A participant may close any remaining planned step during any week.

A participant may close all steps earlier than the end of the challenge.

MVP does not allow participant to add new steps.

If all steps are completed early:
- bot tells participant that all current steps are closed
- bot suggests contacting captain/tracker for the next route
- if final goal is achieved, participant defines a new goal and new steps with captain/tracker
- if final goal is not achieved, participant defines additional steps for the current goal
- captain may approve steps but does not add them to the system
- admin adds new/additional steps in Google Sheets
- reminders continue after new steps are added
- bot must not require closing a non-existent step while new steps are not yet added

Final goal achievement:
- final goal is fixed by tracker
- admin may also fix final goal achievement through Google Sheets
- participant cannot mark final goal as achieved
- captain cannot mark final goal as achieved
- bot must not automatically mark final goal as achieved only because all planned steps are closed

## 9. Weekly focus and step report logic

At the beginning of each week, each participant must select one open planned step as the weekly focus.

Weekly focus rules:
- focus is mandatory when open planned steps exist
- focus can be selected only from open planned steps
- focus cannot be changed inside the same week
- closing the focused step does not require selecting a new focus for the remaining week
- focus does not prevent reporting another step in the same week
- captains and trackers must see weekly focus in reports

Participants report per planned step.

Step status display:
- ⬜ open step / no step report yet
- 🟩 closed step / report submitted for this step

Step report actions:
- open steps show `Отчитаться`
- closed steps show `Редактировать отчёт`

A participant may close any number of open steps in the same week by submitting one report per step.

Captain may manually submit report for participant in own team before deadline.

Late reports after deadline do not change weekly status.

Step selection rules:
- every submitted step report is linked to exactly one planned step
- each planned step has at most one final report
- participants can edit the report text for a closed step before deadline
- editing a step report changes report text and `updated_at`
- editing a step report must not change the original `submitted_at`, `closed_at`, or `closed_week_number`
- already closed steps cannot be closed again

## 10. Deadline

Timezone: `Asia/Yekaterinburg`.

Week closes Sunday 23:59.

After deadline:
- no late yellow status
- no status change from participant
- no late captain manual report
- missing report becomes ⬜
- late report text may be saved, but it must not change the closed week's status

## 11. Weekly schedule

Schedule in `Asia/Yekaterinburg`:

- Monday 10:00: start of week reminder
- Wednesday 10:00: soft check-in
- Sunday 18:00: final check-in
- Sunday 22:30: reminder if no weekly report
- Sunday 23:00: last reminder if no weekly report
- Sunday 23:59: deadline
- Monday 00:00-00:20: close week and generate reports
- Monday 00:20-01:00: send reports

If participant already submitted weekly report, no more reminders that week.

## 12. Progress calculation

Progress is calculated based on planned steps.

Challenge route:
- Week 1: goal formulation
- Week 2: route / planned steps
- Weeks 3-8: six working weeks for step execution
- Main route contains 6 planned steps
- Main progress bar has 6 cells
- Weeks 1-2 are not included in the main progress bar

Scoring:
- 🟩 = 1
- 🟦 = 0.5
- 🟥 = 0
- ⬜ = 0

Progress percent:

completed score / total planned steps * 100

Examples:
- 5 of 6 = 83.3%
- 6 of 6 = 100%

Weekly status history is stored separately from main step progress. UI may show both main progress bar and weekly history, but main progress percent is based only on planned steps.

## 13. Insights

Insights are separate from progress.

Insight does not count as victory.

If participant did nothing but had an insight:
- weekly status remains 🟥 or ⬜ depending on report state
- insight is stored separately

Participant can add insights through menu.

Insights may relate to:
- current week
- previous week
- goal in general

## 14. Participant menu

MVP participant menu:

- 🎯 Моя цель
- 📍 Мои шаги
- 📊 Мой прогресс
- 💡 Мои инсайты

## 15. Captain menu

MVP captain menu:

- 🎯 Моя цель
- 📍 Мои шаги
- 📊 Мой прогресс
- 💡 Мои инсайты
- 👥 Моя команда
- ➕ Внести отчёт за участника
- 📄 Отчёт команды

## 16. Captain manual report

Captain can manually add report only for participants from own team.

Flow:
1. Captain opens menu.
2. Selects "Внести отчёт за участника".
3. Bot shows participants of captain's team.
4. Captain selects participant.
5. Captain selects current week.
6. Captain selects status:
   - 🟩 victory
   - 🟦 partial victory
   - 🟥 no victory
7. For 🟩 or 🟦, captain selects one or more related planned steps.
8. Captain sends text or voice report.
9. Bot saves report before deadline.

Manual captain report must store:
- participant id
- captain id
- team id
- week number
- status
- selected step ids for 🟩 or 🟦
- report text
- transcription if voice
- audio file link if voice
- submitted by captain
- submitted at

Captain cannot submit reports for dropped participants.

## 17. Silent participants

If participant has no weekly report for one week:
- participant is marked as risk zone
- captain receives notification
- tracker receives notification

System does not automatically mark participant as dropped.

Captain and tracker decide what to do.

## 18. Dropped participants

Dropped participants:
- remain visible in reports
- are shown as gray blocks
- are excluded from victory percentage statistics

Dropped status is managed manually through Google Sheets in MVP.

## 19. Voice messages

Voice message limit: 10 minutes.

Voice messages must be transcribed.

Store:
- original audio file
- transcription text
- participant id
- week number
- report or insight relation
- created at

Audio files are stored until one month after the end of challenge.

Audio path structure on VPS:
- `data/audio/{year}/week_{week_number}/{team_name}/{participant_id}/{report_or_insight_id}.ogg`

Audio retention:
- original audio is stored locally on VPS
- audio file path remains in Google Sheets after deletion
- audio is deleted automatically one month after recording
- transcription text remains in Google Sheets after original audio deletion
- reports must show transcription text after audio deletion, not the audio file

If transcription fails:
- participant is asked to repeat voice or send text
- admin receives error notification

## 20. Reports

MVP reports:
- short Telegram report per team
- PDF report per team
- full summary for admin and Sitnikov

## 21. Short Telegram team report

One message per team.

Format:
- week number
- team name
- captain name
- active participants count
- dropped participants count
- weekly victory percentage
- participant list with progress bar and percent

Example:

Week 3
Team: Достигаторы
Captain: Иван Петров

Active: 8
Dropped: 2
Weekly victories: 62.5%

Иванов Иван — 🟩🟦⬜⬜⬜⬜ 25%
Петров Сергей — 🟩🟥⬜⬜⬜⬜ 16.7%

## 22. PDF report

One PDF per team.

PDF first page:
- week number
- team name
- captain name
- active participants count
- dropped participants count
- weekly victory percentage
- progress bars of all participants

PDF should include participant details:
- goal
- goal value
- permission condition
- planned steps
- completed steps
- weekly status
- report text
- transcription text
- insights

PDF retention and access:
- PDF is simple and readable in MVP
- no "Смерть иллюзий" brand styling is required in MVP
- PDF is stored on VPS for 6 months after challenge end
- PDF is not available by public link
- PDF is sent only to authorized recipients by role

## 23. PDF recipients

- captain receives PDF for own team
- Ivan Larkin receives all male team PDFs
- Maria receives all female team PDFs
- admin receives all PDFs
- Sitnikov receives all PDFs

## 24. Group comparison

Group comparison is visible only to:
- admin
- Sitnikov

Do not send group comparison to captains or trackers unless explicitly requested later.

## 25. Error notifications

The system uses three Telegram bots:
- main bot for participant and captain scenarios
- error bot for technical errors only, sent only to admin
- notification bot for operational notifications, PDFs, and summaries

Admin must receive technical error notifications through error bot for:
- participant not found
- unknown Telegram user
- Google Sheets read error
- Google Sheets write error
- SQLite error
- voice transcription error
- PDF generation error
- report sending error
- scheduler error
- invalid dialog state
- missing required data

Technical errors must not be sent to participants, captains, trackers, or Alexander Sitnikov. Ordinary work notifications go through notification bot.

## 26. Security and privacy

Rules:
- do not commit .env
- do not expose bot tokens
- do not expose Google credentials
- do not send personal data to unnecessary chats
- do not include secrets in logs
- restrict access to Google Sheets
- only admin edits Google Sheets structure and primary data directly
- trackers may have direct Google Sheets access but must not change structure, column names, technical IDs, or service fields
- captains and participants do not get direct Google Sheets access
- captain receives full report texts, transcriptions, and insights only for own team
- participant data is only visible according to role

## 27. Out of MVP

Out of MVP:
- web form
- PostgreSQL
- participant-created steps
- participant editing past weeks
- late status
- public group comparison
- payments
- full admin panel
- mobile app
- advanced analytics
- automatic coaching recommendations
- Docker
- Redis
- Celery
- Kubernetes

## 28. Deployment and backups

Production deployment:
- production MVP runs as `systemd` service on VPS
- bot runs 24/7
- manual Python command is allowed for tests
- `systemd` starts bot after reboot and restarts it after process crash
- logs are available through `journalctl`
- dependencies are installed in Python virtual environment `.venv`
- configuration is stored in `.env`
- production launch requires separate test Telegram bot and smoke test

Backups:
- SQLite is backed up daily, automatically, with 14-day retention
- Google Sheets is exported periodically as `.xlsx` or `.csv`, with 14-day retention
- fresh Google Sheets export is recommended before week close and mass report sending
- no mandatory audio backup in MVP
- no mandatory separate PDF backup in MVP
- backup folder: `/root/telegram_goals_bot/backups/`
- `backups/` must not be committed

## 29. Decisions

Product decisions are recorded in `docs/02_open_questions.md`.

Do not guess silently.
