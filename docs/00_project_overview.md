# Project Overview

## Working title

"Трекер целей"

## Context

This project is an MVP Telegram bot for the challenge "Смерть иллюзий" by Alexander Sitnikov.

The bot helps participants, captains, trackers, the admin, and Alexander Sitnikov track weekly progress toward personal goals.

The system does not replace the coach, captain, or tracker. It works as a digital interviewer, data collector, history keeper, reminder system, and report generator.

## Main idea

Each participant has:

- a concrete goal
- a goal value
- a permission condition
- predefined planned steps: 6 main route steps for working weeks
- weekly progress
- insights

The steps are not rigidly tied to specific weeks.

Each week the participant should complete at least one remaining planned step or make meaningful progress toward the goal.

Challenge calendar:
- all teams start simultaneously
- week 1: goal formulation
- week 2: route / planned steps
- weeks 3-8: six working execution weeks
- challenge end date: `2026-07-31`
- all times use `Asia/Yekaterinburg`

## MVP goal

Build a Telegram bot that can:

- identify users by Telegram ID
- request consent on first start
- show participant goal
- show planned steps
- show participant progress
- collect weekly reports
- collect insights
- accept text messages
- accept voice messages up to 10 minutes
- transcribe voice messages
- let captains manually add reports for participants in their own team
- calculate progress
- send weekly reminders
- detect silent participants
- notify captains and trackers about silent participants
- generate short Telegram reports by team
- generate PDF reports by team
- notify admin about errors

## Main users

### Participant

A participant reports weekly progress, views goal, views planned steps, sends insights, and may send voice messages.

### Captain

A captain is also a participant, but has extra responsibility for their team.

Captain receives notifications about silent participants in their team and can manually add reports for participants in their own team.

### Tracker

A tracker supervises several teams.

Ivan Larkin receives male team reports.

Maria receives female team reports.

### Admin

Admin is Alexander.

Admin manages Google Sheets, receives all reports, and receives all error notifications.

### Alexander Sitnikov

Alexander Sitnikov receives all reports and group comparison summaries.

## MVP data storage

Business data is stored in Google Sheets.

Technical dialogue state is stored in SQLite on VPS.

Audio files are stored locally on VPS.

PDF reports are generated and stored locally on VPS before sending.

The MVP uses three Telegram bots:
- main bot for participant/captain scenarios
- error bot for technical errors sent only to admin
- notification bot for operational notifications, PDFs, and summaries

## Reporting

The system generates:

- short Telegram report per team
- PDF report per team
- full summary for admin and Sitnikov

PDF distribution:

- captain receives PDF only for own team
- Ivan Larkin receives all male team PDFs
- Maria receives all female team PDFs
- admin receives all PDFs
- Sitnikov receives all PDFs

Group comparison is visible only to admin and Sitnikov.

## Core constraints

The MVP starts with Telegram.

Web form may be added later.

Participants cannot edit previous weeks.

Participants cannot add new planned steps in MVP.

Late reports after Sunday 23:59 Yekaterinburg time do not change weekly status.

Insights are stored separately and do not replace weekly progress.

Main progress is calculated from the 6 planned steps. Weekly status history is stored separately.

## Development principle

Do not write application code before requirements, architecture, schemas, Telegram scenarios, reports, and MVP plan are documented and approved.
