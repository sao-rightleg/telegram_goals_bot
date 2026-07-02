# Telegram Goals Bot

MVP Telegram-бот для челленджа «Смерть иллюзий».

Бот собирает еженедельные отчёты участников, хранит прогресс по шагам, принимает текстовые и голосовые ответы, помогает капитанам и трекерам видеть состояние команд и формирует Telegram/PDF-отчёты.

## Статус

Проект находится на стадии технического фундамента MVP.

Утверждённые требования, архитектура, схемы данных, Telegram-сценарии, отчёты и MVP-план уже лежат в `docs/`.

Сейчас реализована foundation-часть: структура Python-пакета, конфигурация, redaction секретов, SQLite technical-state schema, scheduler/file path constants и boundary/fake слои для внешних интеграций.

Полные Telegram-сценарии, live Google Sheets/Telegram API интеграции, voice transcription, PDF generation и production deploy в эту foundation-фичу не входят.

## Локальная Проверка Foundation

Один раз подготовить окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Запустить весь foundation test suite:

```bash
source .venv/bin/activate
python -m pytest -v
```

Быстрые smoke-проверки:

```bash
source .venv/bin/activate
python -c "import app; print('ok')"
python -m pytest
```

Тесты используют fake values и временные SQLite базы. Production-секреты, Telegram tokens и Google credentials для этих проверок не нужны.

## Основные решения

- MVP-канал: Telegram.
- Бизнес-данные: Google Sheets.
- Техническое состояние: SQLite на VPS.
- Production runtime: `systemd` на VPS.
- Progress bar: 6 основных planned steps.
- Таймзона: `Asia/Yekaterinburg`.
- Дата окончания челленджа: `2026-07-31`.
- Используются три Telegram-бота: main, error, notification.

## Документация

Основные документы находятся в `docs/`.

Project Knowledge для агентов находится в `.claude/skills/project-knowledge/` и синхронизируется в `.codex/skills/project-knowledge/`.
