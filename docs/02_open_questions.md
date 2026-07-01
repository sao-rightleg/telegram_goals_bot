# Open Questions

This file contains unresolved or partially resolved decisions.

Codex must not silently guess answers to these questions.
If one of these questions affects implementation, ask the user before coding.

## 1. Exact challenge dates

The weekly schedule is defined, but exact start and end dates of the challenge must be confirmed.

Known:
- week starts on Monday
- week ends Sunday 23:59 Yekaterinburg time
- audio files are stored until one month after challenge end
- tentative audio deletion date mentioned: September 30

Need to confirm:
- challenge start date
- challenge end date
- exact number of weeks
- whether all teams start on the same date

## 2. Exact Monday and Wednesday reminder time

Known schedule:
- Monday morning: start of week reminder
- Wednesday evening: soft check-in

Need to confirm exact times:
- Monday reminder time
- Wednesday reminder time

Suggested:
- Monday 10:00 Yekaterinburg time
- Wednesday 18:00 Yekaterinburg time

## 3. Goal achievement status

If participant reaches the final goal early, system should fix victory and notify relevant people.

Need to confirm:
- who marks goal as achieved
- whether participant can mark goal achieved
- whether captain can mark goal achieved
- whether admin changes it in Google Sheets
- what bot should do after goal is achieved

Current assumption:
- goal achievement is fixed manually
- bot does not automatically create new goal

## 4. New route after all steps completed

If participant completes all planned steps before challenge ends, bot congratulates and suggests contacting captain.

Need to confirm:
- can captain add extra steps in MVP
- or are extra steps only edited by admin in Google Sheets
- should bot continue weekly reminders after all steps are closed

Current assumption:
- participant contacts captain
- captain/admin decides manually
- no automatic new steps in MVP

## 5. Captain manual report and step closing

Captain can manually add report for participant.

Need to confirm:
- when captain adds report, must captain select which planned step was closed?
- or only choose weekly status and text report?
- can captain mark a specific step as closed?

Current recommendation:
- captain should select closed planned step if status is green
- for blue status, captain may select related step optionally

## 6. Participant weekly report and step closing

Participant selects weekly status.

Need to confirm:
- if participant selects green, must participant choose which planned step was completed?
- if participant selects blue, should participant choose related step?
- can one weekly report close more than one step?

Current recommendation:
- green requires selecting one or more completed planned steps
- blue may link to one planned step as partially progressed
- allow multiple step closure only if explicitly needed

## 7. Progress bar length

Progress is based on number of planned steps, not fixed number of weeks.

Need to confirm:
- progress bar should show number of planned steps
- or number of challenge weeks
- or both separately

Current recommendation:
- step progress bar shows planned steps
- weekly report history may show weeks separately

## 8. Report terminology

Need to confirm final Russian terms used in bot and reports.

Candidates:
- цель
- шаги
- победа недели
- частичная победа
- нет победы
- инсайт
- капитан
- трекер
- выбывший
- зона риска

## 9. Captain receives personal data

Captain receives PDF for own team and notifications about silent participants.

Need to confirm:
- PDF may include full report text and transcriptions of own team members
- captain is allowed to see all detailed answers of own team

Current assumption:
- yes, captain receives full PDF for own team

## 10. Audio storage path and deletion process

Need to define:
- exact audio folder structure
- deletion script
- whether deletion is manual or scheduled
- whether deleted audio links remain in Google Sheets

Current assumption:
- store audio locally on VPS
- delete one month after challenge end
- keep transcription text permanently

## 11. Google Sheets edit permissions

Admin edits Google Sheets directly.

Need to confirm:
- no captains have direct edit access to Google Sheets
- no trackers have direct edit access to Google Sheets
- all non-admin changes go through bot

Current assumption:
- only admin directly edits Google Sheets

## 12. Error chat implementation

Need to confirm:
- use the same Telegram bot to send errors to a private admin chat
- or create separate error bot

Current recommendation:
- use same bot and a private admin error chat

## 13. PDF design quality

Need to define:
- simple MVP PDF
- or visually polished PDF

Current recommendation:
- clean readable MVP PDF first
- visual polish later

## 14. External skills

Need to decide whether to import external Codex/Claude skills from public repositories.

If importing:
- review contents first
- do not blindly trust scripts
- adapt to this project
- keep project-specific rules in AGENTS.md and docs

Current recommendation:
- use external skills as references
- keep final project skills custom and project-specific

## 15. Production deployment method

Need to define later:
- run bot as systemd service
- use Docker
- use simple Python process for MVP

Current recommendation:
- systemd service on VPS for MVP
- Docker may be added later

## 16. Backups

Need to define:
- Google Sheets backup process
- SQLite backup process
- audio backup process
- PDF backup process

Current recommendation:
- daily backup of SQLite
- Google Sheets version history plus periodic export
- audio backup optional depending on size
