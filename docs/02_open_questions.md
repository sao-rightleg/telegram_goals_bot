# Product Decisions

This file used to contain open questions. The questions below were resolved by `docs/final_product_decisions_for_codex.md`.

Codex must treat these decisions as current source of truth. If older documents conflict with these decisions, the older text is obsolete.

## 1. Challenge Calendar

- All teams use one shared calendar and start simultaneously.
- The challenge has 8 weeks plus 4 days for final summary:
  - Week 1: participants formulate goals.
  - Week 2: participants define route / planned steps.
  - Weeks 3-8: six working weeks for planned step execution.
  - After week 8: four days for final summary.
- Working execution weeks: 6.
- Main route planned steps: 6.
- The first 2 weeks do not count as execution weeks.
- Main progress bar has 6 cells.
- Challenge end date: `2026-07-31`.
- Timezone for all dates, deadlines, and reminders: `Asia/Yekaterinburg`.
- If scheduler needs exact start date, calculate it from `2026-07-31` using 8 weeks + 4 final-summary days.

## 2. Reminders and Deadline

- Monday start-of-week reminder: Monday 10:00.
- Wednesday soft check-in: Wednesday 10:00.
- Sunday final check-in: Sunday 18:00.
- Sunday reminder for missing reports: Sunday 22:30.
- Sunday last reminder for missing reports: Sunday 23:00.
- Hard weekly report deadline: Sunday 23:59.
- After Sunday 23:59, a report may be saved as text but must not change the closed week's status.

## 3. Goal Achievement

- Final goal achievement is fixed by the tracker.
- Admin may also fix final goal achievement through Google Sheets.
- Participant cannot mark final goal as achieved.
- Captain cannot mark final goal as achieved.
- Bot must not automatically mark final goal as achieved only because all planned steps are closed.
- After goal achievement, bot tells the participant that the goal is fixed as achieved and suggests setting a new goal with new steps.
- If the goal is achieved early, participant, captain, and tracker define the next route.
- New goals and new steps are added by admin through Google Sheets.
- All steps may be complete while the final goal is not achieved. In that case, participant creates additional steps for the current goal with captain/tracker, and admin adds them to Google Sheets.

## 4. All Planned Steps Completed Early

- If all planned steps are completed before challenge end, bot tells the participant all current steps are closed.
- Bot suggests contacting captain/tracker to define the next route.
- If goal is achieved, participant sets a new goal and new steps.
- If goal is not achieved, participant creates additional steps for the current goal.
- Captain may approve steps but does not add them to the system.
- Participant formulates new/additional steps.
- Admin adds new/additional steps to Google Sheets.
- After new steps are added, weekly reminders continue.
- If new steps are not yet added, bot must not require closing a non-existent step.

## 5. Participant Step Selection

- Participant reports per planned step.
- Open steps show `⬜` and action `Отчитаться`.
- Closed/reported steps show `🟩` and action `Редактировать отчёт`.
- Participant may close several steps in one week by submitting one report per step.
- One step report closes exactly one planned step.
- A planned step can have only one final report; further changes go through report editing.
- Participant cannot close an already closed step again.
- Editing a step report changes report text and `updated_at`, but not `submitted_at`, `closed_at`, or `closed_week_number`.
- Repeated action can be a separate planned step only if it differs by level, scale, or volume.

## 5a. Weekly Focus

- At the beginning of each week, participant must select one open planned step as weekly focus.
- Weekly focus is mandatory while participant has open planned steps.
- Weekly focus cannot be changed inside the same week.
- If the focused step is closed before week end, bot does not require selecting a new focus.
- Weekly focus does not prevent reporting another step in the same week.
- Weekly focus is shown in `Мои шаги` with `🎯` after the focused step number and before the title.
- Weekly focus is shown to captains and trackers in reports.

## 6. Captain Manual Report

- Captain must select the step or steps related to the manual report.
- For `🟩`, captain must select one or more closed steps.
- For `🟦`, captain must select one or more related steps.
- Captain may close several steps for a participant if the participant actually completed them.
- Captain cannot submit reports for dropped participants.
- Captain can submit reports only for participants from own team.
- After Sunday 23:59, captain cannot submit a report that changes a closed week's status.

## 7. Progress Bar

- Main progress bar shows completion of 6 planned steps.
- Main progress bar has 6 cells.
- No separate 8-cell weekly progress bar is needed.
- Weeks 1-2 do not appear in the main progress bar.
- `🟩` = 1 closed step.
- `🟦` = 0.5 step.
- `🟥` = 0.
- `⬜` = 0.
- Weekly status history is stored separately from the main progress bar.
- UI may show both main step progress and weekly status history, but main progress percentage is calculated only from steps.

## 8. Terminology

Use these terms in bot and reports:

- участник
- капитан
- трекер
- команда
- Александр Ситников
- цель
- шаг
- победа недели
- частичная победа
- нет победы
- нет ответа
- зона риска
- выбывший
- инсайт

MVP does not need more branded wording for "Смерть иллюзий".

Tone: simple, clear, without excessive motivation or coaching pressure.

## 9. Captain Access to Team Data

- Captain may see full report texts of own team participants.
- Captain may see full voice transcription texts of own team participants.
- Captain may see insights of own team participants.
- Captain cannot see data from other teams.
- Captain does not receive group comparison.
- Captain receives only own-team data.

## 10. Audio

Audio path structure on VPS:

```text
data/audio/
  2026/
    week_01/
      team_name/
        participant_001/
          report_001.ogg
```

Rules:

- Original audio files are stored locally on VPS.
- Audio file path is stored in Google Sheets.
- Audio is stored for 1 month after recording.
- Audio is deleted automatically.
- After audio deletion, path remains in Google Sheets.
- Transcription is stored in Google Sheets and remains after original audio deletion.
- Long-term source is transcription text, not original audio.
- If audio file was deleted, system must not try to open or send it as an existing file.
- Reports must show `transcription_text` after audio deletion, not the audio file.

## 11. Google Sheets Access

- Only admin edits Google Sheets directly as owner of structure and data correctness.
- Captains do not get direct Google Sheets access.
- Participants do not get direct Google Sheets access.
- Trackers get direct Google Sheets access.
- All participant and captain changes go through Telegram bot.
- Admin initially fills participants, teams, goals, and steps.
- Telegram bot must tolerate manual edits by trackers.
- Trackers must not change sheet structure, column names, technical IDs, or service fields.

## 12. Bots and Error Notifications

MVP uses three Telegram bots:

- Main bot: participant and captain user scenarios.
- Error bot: technical errors only, sent only to admin.
- Notification bot: operational notifications, PDFs, and summaries for admin, captains, trackers, and Alexander Sitnikov.

Rules:

- Technical errors and ordinary notifications are separated.
- Error chat receives only technical errors.
- Ordinary work notifications go through notification bot.
- Technical errors must not be sent to participants, captains, trackers, or Alexander Sitnikov.
- If three bots complicate implementation, mark it as implementation risk, but do not change the decision without user confirmation.

## 13. PDF

- PDF for MVP is simple and readable.
- No "Смерть иллюзий" brand styling is needed in MVP.
- PDF does not need print-specific preparation.
- PDF is stored on VPS for 6 months after challenge end.
- PDF is not deleted immediately after sending.
- PDF must not be available through a public link.
- PDF is sent only to authorized recipients by role.

## 14. Production Deployment

- Production MVP runs as `systemd` service on VPS.
- Bot must run 24/7.
- Manual Python command is allowed for tests.
- Production uses `systemd service`.
- `systemd` starts bot after VPS reboot.
- `systemd` restarts bot when process crashes.
- Logs are available through `journalctl`.
- Docker is not used in MVP.
- Redis, Celery, Kubernetes, and complex DevOps are not used in MVP.
- Dependencies are installed in Python virtual environment `.venv`.
- Configuration is stored in `.env`.

Manual operations to document:

```bash
systemctl status telegram-goals-bot
systemctl restart telegram-goals-bot
journalctl -u telegram-goals-bot -f
```

Production launch requires a separate test Telegram bot, separate token, and test Google Sheets table or test sheets. Production starts only after smoke test.

Smoke test must cover `/start`, identification, consent, participant menu, weekly report, voice messages, captain manual report, reminders, week closing, PDF generation, and error chat.

## 15. Backups

SQLite:

- Daily automatic backup.
- Retention: 14 days.
- Stores technical state: active dialogues, drafts, temporary states, scheduler state.

Google Sheets:

- Periodic export.
- Daily export or export before important weekly operations is enough for MVP.
- Export format: `.xlsx` or `.csv`.
- Retention: 14 days.
- Fresh copy is recommended before week close and mass report sending.

Audio:

- No mandatory audio backup in MVP.
- Long-term source is transcription text.
- Original audio is stored locally until automatic deletion after 1 month.
- Temporary manual audio archive is allowed for disputed cases but is not part of required MVP.

PDF:

- No mandatory separate PDF backup in MVP.
- PDF is stored locally for 6 months after challenge end.
- PDF can be regenerated from Google Sheets if source data is preserved.
- Final PDFs may be manually saved after challenge end if needed.

Backup location on VPS:

```text
/root/telegram_goals_bot/backups/
```

Structure:

```text
backups/
  sqlite/
  google_sheets_exports/
  pdf/
```

Rules:

- `backups/` must not be committed.
- Backups must not be publicly accessible.
- External backup storage is not added in MVP.

## 16. External Skills

No final product decision changed this item.

If external Codex/Claude skills are imported later:

- Review contents first.
- Do not blindly trust scripts.
- Adapt to this project.
- Keep project-specific rules in Project Knowledge and docs.
