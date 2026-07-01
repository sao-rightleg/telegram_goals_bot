# MVP Plan

## Purpose

This plan defines the documentation and implementation sequence for the "Трекер целей" MVP.

Application code must not be written until requirements, architecture, schemas, Telegram scenarios, reports, and MVP plan are approved.

## MVP Scope

The MVP includes:
- Telegram bot
- user identification by Telegram ID
- consent flow
- participant goal view
- planned steps view
- progress view
- weekly report collection
- insight collection
- text and voice answers
- voice transcription for messages up to 10 minutes
- captain manual reports for own team
- weekly reminders
- deadline closing
- silent participant detection
- captain and tracker notifications about silent participants
- short Telegram reports by team
- PDF reports by team
- full summary for admin and Sitnikov
- admin error notifications
- Google Sheets as business storage
- SQLite as technical state storage
- local audio and PDF storage

## Out of MVP

Do not include:
- web form
- PostgreSQL
- Docker
- Redis
- Celery
- web admin panel
- participant-created steps
- editing past weeks
- late status
- public group comparison
- payments
- mobile app
- advanced analytics
- automatic coaching recommendations

## Approval Gates

Before coding:
1. Requirements approved.
2. Architecture approved.
3. Google Sheets schema approved.
4. SQLite state schema approved.
5. Telegram scenarios approved.
6. Report formats approved.
7. MVP implementation plan approved.
8. Blocking open decisions resolved.

## Proposed Work Sequence

### Phase 1. Documentation Approval

Deliverables:
- `docs/03_architecture.md`
- `docs/04_google_sheets_schema.md`
- `docs/05_sqlite_state_schema.md`
- `docs/06_telegram_scenarios.md`
- `docs/07_reports.md`
- `docs/08_mvp_plan.md`

Exit criteria:
- user approves docs
- open questions are accepted or resolved
- no MVP scope violations remain

### Phase 2. Data Preparation

Deliverables:
- approved Google Sheets structure
- required sheet tabs
- required columns
- allowed values
- sample rows for testing
- final participant/team/captain/tracker data import process

Exit criteria:
- bot can identify participants by Telegram ID
- active participants have team, captain, tracker, goal, and planned steps
- consent fields exist
- report and insight write targets exist

### Phase 3. Technical Skeleton

Deliverables:
- application structure
- configuration loading
- logging
- Telegram bot startup
- Google Sheets client boundary
- SQLite connection and schema setup
- role and permission service boundaries

Exit criteria:
- no secrets in code
- `.env.example` contains placeholders only
- generated files and credentials are ignored
- bot can start in test mode

### Phase 4. Core Participant Flows

Deliverables:
- `/start`
- Telegram ID identification
- consent flow
- participant menu
- goal view
- planned steps view
- progress view
- weekly report flow
- insight flow

Exit criteria:
- known user can use menu
- unknown user receives approved message
- admin receives unknown-user error
- weekly report saves to Google Sheets
- insight saves separately from progress

### Phase 5. Voice Processing

Deliverables:
- voice duration validation
- local audio save
- transcription integration
- draft attachment to report or insight
- transcription failure handling
- admin error notification

Exit criteria:
- voice under 10 minutes works
- voice over 10 minutes is rejected
- failed transcription asks user to retry or send text
- audio paths and transcriptions are linked to correct participant and week

### Phase 6. Captain Flows

Deliverables:
- captain menu
- own team view
- manual report for own team participant
- captain deadline protection
- captain PDF access for own team

Exit criteria:
- captain sees only own team
- captain cannot report for other teams
- captain cannot add status-changing report after deadline
- submitted source and role are stored correctly

### Phase 7. Scheduler and Deadlines

Deliverables:
- Monday reminder
- Wednesday check-in
- Sunday 18:00 check-in
- Sunday 22:30 reminder
- Sunday 23:00 reminder
- Sunday 23:59 week closing
- Monday report generation window
- Monday report sending window
- idempotency for duplicate runs

Exit criteria:
- reminders are not sent after report exists
- missing reports become `⬜`
- no yellow late status exists
- duplicate scheduler run does not duplicate reports or reminders

### Phase 8. Reports

Deliverables:
- short Telegram team report
- PDF team report
- full summary for admin and Sitnikov
- group comparison only for admin and Sitnikov
- report delivery routing
- report generation error handling

Exit criteria:
- captain receives only own team PDF
- trackers receive assigned team reports
- admin receives all reports and errors
- Sitnikov receives all reports and group comparison
- captains and trackers do not receive group comparison

### Phase 9. QA and Security Review

Deliverables:
- role permission tests
- deadline tests
- Google Sheets error tests
- SQLite state recovery tests
- voice processing tests
- report generation and routing tests
- privacy/security review

Exit criteria:
- no critical role leakage
- no secrets in repo
- `.gitignore` protects generated and sensitive files
- failures notify admin where required
- manual sheet data validation catches core problems

### Phase 10. MVP Deployment Preparation

Deliverables:
- production config checklist
- VPS folder structure
- systemd service plan if approved
- backup plan
- audio/PDF retention plan
- admin smoke test checklist

Exit criteria:
- deployment method approved
- backups and retention decisions documented
- admin error chat tested
- basic restart behavior tested

## MVP Success Criteria

MVP is ready when:
- participants can submit weekly reports
- captains can submit reports for own team before deadline
- reminders work according to schedule
- silent participants are detected and routed to captain/tracker
- weekly statuses and progress calculate correctly
- insights are stored separately
- voice messages are stored and transcribed
- reports are generated and sent to correct recipients
- admin receives required errors
- no out-of-MVP infrastructure or features were added

## Key Risks

- Unresolved challenge dates can break week numbering and audio retention.
- Ambiguous step-closing rules can break progress calculation.
- Progress bar meaning must be clarified before final report implementation.
- Manual Google Sheets edits can break IDs or role permissions.
- Voice transcription failures must not lose participant answers.
- Wrong report routing can leak personal data.
- Duplicate scheduler runs can create duplicate reminders or gray reports unless idempotent.

## Open Questions / Decisions Needed

- Exact challenge start and end dates.
- Exact number of weeks.
- Exact Monday and Wednesday reminder times.
- Who marks final goal achievement.
- What happens after all planned steps are completed early.
- Step selection rules for participant reports.
- Step selection rules for captain manual reports.
- Final progress bar meaning.
- Final Russian terminology.
- Captain access to full report text and transcriptions.
- Audio storage path and deletion process.
- Google Sheets direct edit permissions confirmation.
- Error chat implementation.
- PDF design quality.
- Production deployment method.
- Backup policy.
