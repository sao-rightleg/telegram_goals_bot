---
name: telegram-dialog-design
description: Use when designing or reviewing Telegram bot conversations, menus, buttons, reminders, consent flow, weekly reports, insights, and captain manual report flows for the goal tracker MVP.
---

# Telegram Dialog Design

Use this skill for user-facing Telegram scenarios in "Трекер целей".

## Required context

Read:
- `AGENTS.md`
- `docs/01_requirements.md`
- `.codex/agents/conversation-designer.md`
- `.codex/agents/telegram-bot-engineer.md`

## Tone

User-facing messages must be in Russian:
- short
- clear
- calm
- practical
- respectful
- not coaching
- not therapeutic
- not motivational

Avoid long explanations, pressure, and unnecessary emojis.

## Core flows

Design or review:
- first start and consent
- unknown user handling
- participant menu
- captain menu
- weekly report status selection
- green, blue, and red report collection
- multiple text or voice messages before `✅ Готово`
- insight add/view flow
- captain manual report flow
- reminder wording
- deadline rejection messages
- broken-state recovery

## Hard rules

- Consent is required before continuing.
- Unknown users get the approved not-in-base message and admin is notified.
- Captains see only their own team.
- Participants do not see other participants' data.
- Do not allow late status changes after Sunday 23:59 Yekaterinburg time.
- Do not create yellow late status.
- Insights do not change progress or weekly status.
- Drafts and active flow state belong in SQLite.
- Final business facts belong in Google Sheets.

## Output

Provide:
- flow steps
- exact Russian bot messages
- buttons
- saved data
- failure states
- open questions

Do not write application code unless the user explicitly asks after approval.
