# Reports

## Purpose

Reports show weekly progress for captains, trackers, admin, and Alexander Sitnikov.

Reports must be concise, role-aware, readable, and generated from stored Google Sheets business data.

## MVP Report Types

MVP includes:
- short Telegram report per team
- PDF report per team
- full summary for admin and Sitnikov
- group comparison for admin and Sitnikov only

Out of MVP:
- public leaderboard
- advanced analytics
- coaching recommendations
- public group comparison

## Statuses and Scoring

Allowed statuses:
- `🟩` victory / completed planned step
- `🟦` partial victory
- `🟥` no victory
- `⬛` deadline passed, no report submitted
- `⬜` current/future week whose deadline has not passed; display placeholder only

Do not use yellow late status.

Scoring:
- `🟩` = 1
- `🟦` = 0.5
- `🟥` = 0
- `⬛` = 0

Progress percent:

```text
completed score / total planned steps * 100
```

Dropped participants:
- remain visible in reports
- are shown separately or as gray blocks
- are excluded from victory percentage statistics

Insights:
- are shown separately
- do not count as progress
- do not change weekly status

## Recipients

### Captain

Receives:
- short Telegram report for own team
- PDF report for own team
- notifications about silent participants in own team
- full report texts for own team participants
- full voice transcriptions for own team participants
- insights for own team participants

Does not receive:
- reports for other teams
- group comparison
- admin errors

### Tracker

Receives reports for assigned teams:
- Ivan Larkin receives male team reports.
- Maria receives female team reports.

Does not receive:
- unrelated teams
- group comparison unless explicitly changed later

### Admin

Admin is Alexander.

Receives:
- all team reports
- all PDFs
- all error notifications
- group comparison

### Alexander Sitnikov

Receives:
- all reports
- all PDFs
- group comparison summaries

## Short Telegram Team Report

One message per team.

Required fields:
- week number
- team name
- captain name
- active participants count
- dropped participants count
- submitted reports count and percentage of active participants
- missing reports count and percentage of active participants
- names of participants with missing reports
- weekly victory percentage
- participant list with progress bar and percent

Recommended Russian format:

```text
Неделя {week_number}
Команда: {team_name}
Капитан: {captain_name}

Активных: {active_count}
Выбывших: {dropped_count}
Победы недели: {weekly_victory_percent}%

{participant_full_name} — {progress_bar} {progress_percent}%
{participant_full_name} — {progress_bar} {progress_percent}%
```

## PDF Team Report

One PDF per team.

### First Page

Must include:
- week number
- team name
- captain name
- active participants count
- dropped participants count
- weekly victory percentage
- progress bars of all participants

### Team Summary

Include:
- current week status distribution
- number of green statuses
- number of blue statuses
- number of red statuses
- number of no-answer statuses
- participants in risk zone
- dropped participants

### Participant Section

For each participant:
- full name
- username if available
- weekly status
- progress bar
- progress percent
- goal title
- goal description
- goal value
- permission condition
- planned steps
- completed steps
- current weekly report text
- transcription text if voice was used
- insights

### Dropped Participants Section

Dropped participants must remain visible.

They should be visually separated from active participants and excluded from active victory percentage statistics.

## Full Summary for Admin and Sitnikov

Include:
- week number
- all team summaries
- overall submitted and missing report counts with percentages of all active participants
- a per-team breakdown of submitted and missing report counts and percentages
- names of participants with missing reports inside each team block
- risk zones
- dropped counts
- high-level comparison between groups
- report generation errors if relevant for admin

Do not add coaching recommendations.

Tracker summaries use the same structure but include only assigned teams. Captain summaries use the same submission and missing-report metrics for the captain's own team. Dropped participants remain visible where required but are excluded from the denominator. Percentages are rounded to one decimal place, with integer percentages displayed without a trailing decimal zero.

## Group Comparison

Visible only to:
- admin
- Alexander Sitnikov

Do not send group comparison to:
- captains
- trackers

Unless this rule is explicitly changed later.

## Progress Bar

Main progress bar:
- shows completion of 6 planned steps
- has 6 cells
- does not include weeks 1-2
- is the source for main progress percent

Scoring:
- `🟩` = 1 closed step
- `🟦` = 0.5 step
- `🟥` = 0
- `⬜` = 0

Weekly status history is stored separately from the main progress bar. UI and reports may show both, but the main progress percent is calculated only from planned steps.

In weekly history, `⬜` is reserved for current/future weeks. In the planned-step progress bar below, `⬜` continues to mean an open planned step.

Example:

```text
Иванов Иван — 🟩🟦⬜⬜⬜⬜ 25%
```

## Data Sources

Reports use Google Sheets as source of final business facts.

Role reports are generated only from final weekly facts. If an active participant has no final `WeeklyReports` row, generation must fail and notify the administrator instead of classifying the participant as overdue. Unknown status codes must also fail validation.

Required data:
- participants
- teams
- captains
- trackers
- goals
- planned steps
- weekly reports
- insights
- dropped status
- risk status
- report metadata

SQLite may store report job state but must not be the source of final report facts.

## File Storage

PDF files:
- generated locally on VPS
- stored in non-public folder
- sent only to authorized recipients
- not exposed as public links
- not committed to repository
- stored for 6 months after challenge end
- not deleted immediately after sending

Recommended folder:
- `reports/pdf/`

If original audio has already been deleted by retention cleanup, reports must show `transcription_text` and must not try to attach or open the deleted audio file.

## Error Handling

If PDF generation fails:
- log error
- notify admin
- do not silently skip report

If Telegram summary sending fails:
- log error
- notify admin

If one recipient is missing Telegram ID or sending fails:
- notify admin
- continue sending to other authorized recipients

## MVP PDF Style

Use clean readable MVP PDF:
- clear sections
- readable font size
- simple tables
- obvious status meanings
- no unnecessary decoration
- suitable for phone and desktop reading
- no special "Смерть иллюзий" brand styling
- no print-specific preparation requirement

## Product Decisions

Resolved product decisions are recorded in `docs/02_open_questions.md`.

Long voice transcriptions may be shown in participant sections or appendix; choose the readable option during PDF implementation without changing access rules.
