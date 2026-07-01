# Project

## Purpose

"Трекер целей" is an MVP Telegram bot for the "Смерть иллюзий" challenge by Alexander Sitnikov.

The bot is a digital interviewer, data collector, history keeper, reminder engine, and report generator. It is not a coach, therapist, motivator, or advice engine.

## MVP Channel

The MVP starts with Telegram only.

A web form may be added later, but the MVP must not implement it. Architecture must avoid blocking a future additional channel.

## Main Users

- Participant: reports weekly progress, views goal, views planned steps, views progress, sends insights, sends text and voice messages.
- Captain: participant with team responsibilities; receives own-team silent participant notifications, may manually add reports for own team, receives own-team PDF.
- Tracker: supervises assigned teams. Ivan Larkin receives male team reports. Maria receives female team reports.
- Admin: Alexander. Manages Google Sheets, receives all reports, receives all errors.
- Alexander Sitnikov: receives all reports and group comparison summaries.

## MVP Scope

Included:

- Telegram ID identification.
- Consent flow.
- Participant goal, planned steps, and progress views.
- Weekly report collection.
- Insight collection.
- Text answers and voice answers up to 10 minutes.
- Voice transcription.
- Captain manual reports for own team before deadline.
- Weekly reminders and deadline closing.
- Silent participant detection.
- Captain and tracker notifications about silent participants.
- Short Telegram reports by team.
- PDF reports by team.
- Full summary for admin and Alexander Sitnikov.
- Admin error notifications.
- Google Sheets as business storage.
- SQLite as technical state storage.
- Local audio and PDF storage.
- Three Telegram bots: main bot, error bot, notification bot.

Out of MVP:

- Web form.
- PostgreSQL.
- Docker, Redis, Celery.
- Web admin panel.
- Participant-created steps.
- Editing past weeks.
- Yellow late status.
- Public group comparison.
- Payments, mobile app, advanced analytics, automatic coaching recommendations.

## Challenge Calendar

- All teams use one shared calendar.
- Challenge end date: `2026-07-31`.
- Week 1: goal formulation.
- Week 2: route / planned steps.
- Weeks 3-8: six working execution weeks.
- After week 8: four days for final summary.
- Main route has 6 planned steps and a 6-cell progress bar.
- Timezone: `Asia/Yekaterinburg`.

## Source Documents

Detailed project documentation lives in `docs/`. The current implementation sequence is in `docs/08_mvp_plan.md`.
