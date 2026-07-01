# Architecture

## Purpose

This document describes the MVP architecture for "Трекер целей".

The goal is to support the approved Telegram-based MVP without adding infrastructure or features that are outside the current scope.

## MVP Principles

- Telegram bot is the only MVP user interface.
- Google Sheets is the main business database.
- SQLite on VPS stores only technical bot state and temporary dialogue state.
- Audio files are stored locally on VPS.
- PDF reports are generated and stored locally on VPS before sending.
- The scheduler runs reminders, week closing, report generation, and report sending.
- Admin receives Telegram error notifications.

Out of MVP:
- PostgreSQL
- Docker
- Redis
- Celery
- web admin panel
- advanced analytics
- public group comparison
- automatic coaching recommendations

## High-Level Architecture

```text
Telegram users
  |
  v
Telegram Bot Layer
  |
  +--> Dialogue State Layer --> SQLite
  |
  +--> Business Services
          |
          +--> Google Sheets Integration --> Google Sheets
          +--> Voice Processing -----------> local audio files + transcription provider
          +--> Report Generation ----------> local PDF files
          +--> Notification Routing -------> Telegram recipients
          +--> Scheduler ------------------> reminders, closing, reports
```

## Components

### Telegram Bot Layer

Responsibilities:
- receive Telegram updates
- identify users by Telegram ID
- check consent
- route commands and button callbacks
- show role-based menus
- collect reports, insights, and voice messages
- call business services
- send messages, reminders, reports, and errors

Rules:
- keep handlers thin
- do not call Google Sheets directly from handlers
- do not store final business facts only in memory or SQLite
- do not expose internal IDs to users

### Business Services

Responsibilities:
- enforce participant, captain, tracker, admin, and Sitnikov rules
- calculate progress
- validate weekly status and deadline rules
- prepare data for Google Sheets writes
- prepare data for reports
- keep business logic independent from Telegram details

Core services:
- participants
- teams
- goals
- planned steps
- weekly reports
- insights
- progress
- notifications
- permissions

### Google Sheets Integration Layer

Responsibilities:
- read participants, teams, trackers, goals, planned steps, weekly reports, and insights
- write consent, weekly reports, insights, report metadata, and status updates
- validate required fields before write
- isolate Google API details from the rest of the app

Google Sheets stores final business facts.

### SQLite Dialogue State Layer

Responsibilities:
- active flow state
- current step in dialogue
- draft report and insight messages
- selected participant for captain manual report
- selected status and week
- temporary voice transcription state
- scheduler job state and run history
- technical error events if needed

SQLite does not replace Google Sheets as business storage.

### Voice Processing Layer

Responsibilities:
- check voice message duration
- download Telegram voice files
- save original audio locally
- transcribe voice messages
- attach transcription to current draft/report/insight
- notify admin if transcription fails

Voice limit: 10 minutes.

### Scheduler Layer

Responsibilities:
- Monday 10:00 start-of-week reminder
- Wednesday 10:00 soft check-in
- Sunday 18:00 final check-in
- Sunday 22:30 reminder for participants without weekly report
- Sunday 23:00 last reminder for participants without weekly report
- Sunday 23:59 deadline closing
- Monday 00:00-00:20 close week and generate reports
- Monday 00:20-01:00 send reports

All schedule logic uses Yekaterinburg time.
Timezone identifier: `Asia/Yekaterinburg`.

Challenge calendar:
- all teams share one calendar
- challenge end date is `2026-07-31`
- week 1 is goal formulation
- week 2 is route / planned steps
- weeks 3-8 are six working execution weeks
- after week 8 there are four days for final summary
- if scheduler needs exact start date, calculate it from `2026-07-31` using 8 weeks plus 4 final-summary days

Jobs must be idempotent where possible:
- no duplicate reminders for the same participant, week, and reminder type
- no duplicate gray weekly reports
- no duplicate report sending records

### Report Generation Layer

Responsibilities:
- generate short Telegram team summaries
- generate one PDF report per team
- generate full summary for admin and Sitnikov
- generate group comparison only for admin and Sitnikov
- store generated PDF files locally before sending

Reports must be generated from Google Sheets business data, not SQLite drafts.

### Notification Routing Layer

Responsibilities:
- route participant and captain messages through main bot
- route technical errors through error bot to admin only
- route operational notifications, PDFs, and summaries through notification bot
- send captain notifications for own team
- send tracker reports for assigned teams
- send all reports to admin
- send all reports and group comparison to Sitnikov
- prevent data from being sent to unauthorized roles

The MVP uses three Telegram bots:
- main bot for participant and captain scenarios
- error bot for technical errors only
- notification bot for operational notifications and report delivery

If three bots increase implementation complexity, document it as implementation risk. Do not collapse the design to one bot without user confirmation.

### File Storage Layer

Responsibilities:
- define local audio paths
- define local PDF paths
- check file existence before sending
- support cleanup and retention rules
- avoid public file links

Recommended local folders:
- `data/audio/`
- `data/sqlite/`
- `reports/pdf/`
- `logs/`
- `backups/sqlite/`
- `backups/google_sheets_exports/`
- `backups/pdf/`

Audio path structure:
- `data/audio/{year}/week_{week_number}/{team_name}/{participant_id}/{report_or_insight_id}.ogg`

Retention:
- original audio is deleted automatically one month after recording
- transcription remains in Google Sheets after audio deletion
- PDFs are stored locally for 6 months after challenge end
- generated PDFs must not be publicly accessible

Generated files and secrets must not be committed.

## Data Boundaries

### Business Data in Google Sheets

Google Sheets stores:
- participant profile
- team membership
- captain and tracker assignments
- consent
- goals
- planned steps
- weekly reports
- insights
- dropped and risk status
- report metadata

### Technical Data in SQLite

SQLite stores:
- active dialogue state
- drafts
- temporary selections
- message buffers
- scheduler run state
- retry state
- technical error events

SQLite must not be the only source of final business facts.

## Role Access Boundaries

### Participant

Can access:
- own goal
- own planned steps
- own progress
- own insights
- own weekly report flow

Cannot access:
- other participants
- team private reports
- group comparison
- admin errors

### Captain

Can access:
- own participant features
- own team view
- manual report flow for own team
- notifications about silent participants in own team
- PDF report for own team
- full report texts, voice transcriptions, and insights for own team

Cannot access:
- other teams
- group comparison
- admin errors

### Tracker

Can receive reports and notifications for assigned teams:
- Ivan Larkin: male teams
- Maria: female teams

Trackers may have direct Google Sheets access, but must not change sheet structure, column names, technical IDs, or service fields.

### Admin

Admin is Alexander.

Can access:
- all reports
- all errors
- Google Sheets management

### Alexander Sitnikov

Can receive:
- all reports
- group comparison summaries

## Configuration

Use environment variables or protected credential files for:
- main Telegram bot token
- error Telegram bot token
- notification Telegram bot token
- Google Sheets ID
- Google credentials path
- admin Telegram ID
- admin error chat ID
- Sitnikov Telegram ID
- tracker Telegram IDs
- transcription provider key
- app timezone
- SQLite database path
- audio storage directory
- PDF storage directory
- log level

Do not hardcode production IDs, tokens, chat IDs, or credentials in source code.

## Production Runtime

Production MVP runs as a `systemd` service on VPS.

Runtime rules:
- bot runs 24/7
- manual Python command is allowed for tests
- `systemd` starts the bot after VPS reboot
- `systemd` restarts the bot after process crash
- logs are read through `journalctl`
- dependencies are installed in `.venv`
- configuration is stored in `.env`
- Docker, Redis, Celery, Kubernetes, and complex DevOps are out of MVP

Manual operations to document:
- `systemctl status telegram-goals-bot`
- `systemctl restart telegram-goals-bot`
- `journalctl -u telegram-goals-bot -f`

Production requires a separate test Telegram bot and smoke test before launch.

## Backup Architecture

SQLite:
- daily automatic backup
- 14-day retention

Google Sheets:
- periodic `.xlsx` or `.csv` export
- 14-day retention
- fresh export recommended before week close and mass report sending

Audio:
- no mandatory backup in MVP
- transcription text is the long-term source

PDF:
- no mandatory separate backup in MVP
- PDF can be regenerated from Google Sheets if source data remains

Backup location: `/root/telegram_goals_bot/backups/`.

## Error Handling

Admin must receive Telegram error notifications for:
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

Error messages should contain enough context to fix the issue but must not expose secrets or unnecessary personal data.

## Future Compatibility

The MVP should not implement web form, web admin panel, or PostgreSQL.

However, architecture should avoid blocking a future channel or storage migration:
- keep business logic out of Telegram handlers
- keep Google Sheets access behind integration/repository boundaries
- use stable internal IDs
- keep report generation separate from transport
- keep notification routing role-aware

## Product Decisions

Resolved product decisions are recorded in `docs/02_open_questions.md`.
