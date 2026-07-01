# AGENTS.md

## Project

This project is a Telegram-based goal tracking system for the challenge "Смерть иллюзий".

Working name in user-facing messages: "Трекер целей".

The project is currently in MVP stage.

## Core rule

Do not write application code until the project documentation, architecture, data model, and scenarios are explicitly approved.

When working in this repository, first think as a product team:
- Product Owner
- System Architect
- Conversation Designer
- Database / Google Sheets Designer
- Telegram Bot Engineer
- Report Designer
- QA Engineer
- Security Reviewer
- DevOps Engineer

## MVP channel

The MVP starts with Telegram bot.

Web form may be added later, but the architecture must allow adding it later without rewriting the whole system.

## Data storage decision

For MVP:
- Google Sheets is the main business database.
- SQLite on VPS is used only for technical bot state and temporary dialogue state.
- Audio files are stored locally on VPS.
- PDF reports are generated and stored locally on VPS before sending.

Do not introduce PostgreSQL in MVP unless explicitly requested.

## Business entities

The system works with:
- participants
- captains
- trackers
- admin
- Alexander Sitnikov
- teams
- goals
- planned steps
- weekly reports
- insights
- audio files
- transcriptions
- PDF reports
- notifications
- errors

## Roles

### Participant

Participant can:
- view their goal
- view planned steps
- view progress
- add weekly report
- add insight
- send text
- send voice message up to 10 minutes

Participant cannot:
- edit previous weeks
- change previous week status after deadline
- add new planned steps in MVP

### Captain

Captain is also a participant with extra role.

Captain can:
- receive notifications only about their team
- manually add a report for a participant from their own team
- receive PDF report only for their own team

Captain cannot:
- add reports after the official deadline
- edit reports outside their own team

### Tracker

Trackers:
- Ivan Larkin receives reports for all male teams
- Maria receives reports for all female teams

Tracker can view their groups' reports.

### Admin

Admin is Alexander.

Admin receives all reports, all errors, and manages Google Sheets.

### Alexander Sitnikov

Alexander Sitnikov receives all reports and group comparison summaries.

## Captain logic

Each team has one captain.

Each participant belongs to one team and one captain.

Captain is the first operational contact for silent participants.

If participant is silent for one week, system notifies:
- captain of the team
- tracker of the team

The system does not automatically mark the participant as dropped.

Captain and tracker decide what to do.

## Goal logic

Goal is a concrete desired object or result.

Goal is not just money.

Goal has:
- goal title
- goal description
- goal value amount
- goal value currency
- permission condition
- permission metric amount
- permission metric unit

Example:
Goal: "Комплект мебели домой"
Goal value: 100 000 RUB
Permission condition: "Заработать 300 000 ₽ в бизнесе за 2 месяца"

## Planned steps logic

Participants have predefined planned steps.

Steps are not rigidly tied to specific weeks.

Each week participant should complete at least one of the remaining planned steps.

A participant may complete all steps earlier than the challenge end.

MVP does not allow participant to add new planned steps.

## Weekly status logic

Participant chooses weekly status:
- green: victory / planned step completed
- blue: partial victory
- red: no victory
- gray: no answer before deadline

Use symbols:
- 🟩 completed victory
- 🟦 partial victory
- 🟥 no victory
- ⬜ no answer

Do not use yellow late status.

Late reports after Sunday 23:59 Yekaterinburg time do not change the weekly status.

## Scoring

Progress is calculated from planned steps.

Green status = 1 point.
Blue status = 0.5 point.
Red status = 0 points.
Gray status = 0 points.

Progress percent = completed score / total planned steps * 100.

Dropped participants are visible in reports as gray blocks but excluded from victory percentage statistics.

## Insights

Insights are separate from progress.

If participant did no action but got an insight, weekly status is not counted as victory.

Insight is saved separately.

Insights do not replace action.

## Weekly schedule

Timezone: Yekaterinburg time.

Schedule:
- Monday morning: start of week reminder
- Wednesday evening: soft check-in
- Sunday 18:00: final check-in
- Sunday 22:30: reminder if no weekly report
- Sunday 23:00: last reminder if no weekly report
- Sunday 23:59: deadline
- Monday 00:00-00:20: close week and generate reports
- Monday 00:20-01:00: send reports

If participant already submitted weekly report, do not send more reminders that week.

## Voice messages

Participant may send voice messages up to 10 minutes.

Voice messages must be transcribed.

Store:
- original audio file
- transcription text
- participant id
- week number
- message date
- related report or insight

Audio files are stored until one month after challenge end.

If voice recognition fails:
- ask participant to repeat voice message or send text
- notify admin in error chat

## Reports

MVP reports:
- short Telegram report per team
- PDF report per team
- full summary for admin and Sitnikov

Team Telegram report format:
- week number
- team name
- captain name
- active count
- dropped count
- weekly victory percentage
- participant list with progress bars and percent

PDF recipients:
- captain receives PDF for own team
- Ivan Larkin receives all male team PDFs
- Maria receives all female team PDFs
- admin receives all PDFs
- Sitnikov receives all PDFs

Group comparison is visible only to:
- admin
- Sitnikov

## PDF first page

PDF first page must include:
- week number
- team name
- captain name
- active participants count
- dropped participants count
- weekly victory percentage
- progress bars of all participants

## Error notifications

Create an error notification channel.

Errors to notify admin about:
- participant not found
- Google Sheets write error
- voice transcription error
- PDF generation error
- report sending error
- scheduler error
- unknown Telegram user
- invalid state
- missing required data

## Security

The project handles personal data.

Rules:
- do not commit .env
- do not expose tokens
- do not send personal data to unnecessary chats
- do not include secrets in logs
- restrict access to Google Sheets
- store only necessary data
- require participant consent before using the bot

Consent text:
"Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору и Александру Ситникову в рамках челленджа."

If participant does not consent, bot must not continue.

## Development workflow

Before coding:
1. Read AGENTS.md.
2. Read docs/.
3. Update requirements if needed.
4. Propose architecture.
5. Ask for approval.
6. Only then write code.

Do not silently change business logic.

If a requirement is unclear, write it to docs/02_open_questions.md.

## Code style expectations

Use clear modular structure.

Keep Telegram bot logic separate from:
- Google Sheets integration
- SQLite state storage
- voice transcription
- report generation
- scheduler
- notification routing

Prefer simple MVP implementation over overengineering.

But do not make design choices that block future migration to PostgreSQL or web form.

## Current priority

Current priority is to prepare:
- requirements
- architecture
- Google Sheets schema
- SQLite state schema
- Telegram scenarios
- report structure
- MVP implementation plan

Application code is not the current priority.
