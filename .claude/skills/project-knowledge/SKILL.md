---
name: project-knowledge
description: |
  Use when you need information about this project's architecture, tech stack,
  business rules, data model, Telegram scenarios, reporting, deployment setup,
  coding patterns, security rules, or UX guidelines.
---

# Project Knowledge

This skill is the single source of truth for how this project works and how agents should operate in it.

## Core References

- [project.md](references/project.md) - Project purpose, users, MVP scope, and constraints.
- [requirements.md](references/requirements.md) - Business rules, approval gates, and open decisions.
- [architecture.md](references/architecture.md) - MVP architecture, component boundaries, storage boundaries.
- [patterns.md](references/patterns.md) - Development workflow, coding boundaries, testing, security rules.
- [deployment.md](references/deployment.md) - Deployment assumptions, environment variables, operational notes.
- [ux-guidelines.md](references/ux-guidelines.md) - Telegram bot tone, Russian copy rules, role-aware UX.

## Existing Detailed Docs

The `docs/` directory contains detailed working documents:

- `docs/00_project_overview.md`
- `docs/01_requirements.md`
- `docs/02_open_questions.md`
- `docs/03_architecture.md`
- `docs/04_google_sheets_schema.md`
- `docs/05_sqlite_state_schema.md`
- `docs/06_telegram_scenarios.md`
- `docs/07_reports.md`
- `docs/08_mvp_plan.md`

When implementing or planning a feature, read the specific detailed docs relevant to that task.

