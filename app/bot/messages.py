"""Russian Telegram copy and read-only view formatters."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.insight_models import InsightListItem, InsightPage
from app.services.participant_models import Goal, PlannedStep, WeeklyStatus
from app.services.weekly_report_models import WeeklyReportStatus


UNKNOWN_USER_TEXT = "Извините, вас нет в базе участников. Свяжитесь со своим капитаном."
CONSENT_TEXT = (
    "Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору "
    "и Александру Ситникову в рамках челленджа."
)
CONSENT_ACCEPT_BUTTON = "✅ Согласен"
MISSING_DATA_TEXT = "Данные пока не заполнены. Свяжитесь со своим капитаном."
NOT_AVAILABLE_TEXT = "Раздел будет доступен позже."

VOICE_ACCEPTED_TEXT = "Голосовое принято и расшифровано."
VOICE_TOO_LONG_TEXT = "Голосовое длиннее 10 минут. Отправь, пожалуйста, более короткое голосовое или текст."
VOICE_PROCESSING_FAILED_TEXT = "Не удалось распознать голосовое. Надиктуй ещё раз или напиши текстом для верности."
VOICE_NO_ACTIVE_DRAFT_TEXT = "Сначала начни отчёт или инсайт, потом отправь голосовое."

WEEKLY_REPORT_GREEN_BUTTON = "🟩 Победа есть"
WEEKLY_REPORT_BLUE_BUTTON = "🟦 Частично"
WEEKLY_REPORT_RED_BUTTON = "🟥 Победы нет"
WEEKLY_REPORT_DONE_BUTTON = "✅ Готово"

WEEKLY_REPORT_STATUS_PROMPT_TEXT = "Выбери статус недели."
WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT = "Выбери один или несколько открытых шагов."
WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT = "Выбери один или несколько шагов с частичным прогрессом."
WEEKLY_REPORT_EMPTY_TEXT = "Отправь текст отчёта, потом нажми «✅ Готово»."
WEEKLY_REPORT_LATE_TEXT = "Дедлайн недели уже прошёл. Отчёт не может изменить статус."
WEEKLY_REPORT_DUPLICATE_TEXT = "Отчёт за эту неделю уже принят."
WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT = "Голосовые отчёты будут доступны позже. Сейчас отправь текст."
WEEKLY_REPORT_RECOVERY_TEXT = "Черновик отчёта сброшен. Начни отправку отчёта заново."
WEEKLY_REPORT_GREEN_SUCCESS_TEXT = "Принято. Победа недели сохранена."
WEEKLY_REPORT_BLUE_SUCCESS_TEXT = "Принято. Частичная победа сохранена."
WEEKLY_REPORT_RED_SUCCESS_TEXT = "Принято. Отчёт за неделю сохранён."

CAPTAIN_TEAM_TITLE_TEXT = "Твоя команда:"
CAPTAIN_ONLY_TEXT = "Этот раздел доступен только капитану."
CAPTAIN_NO_TEAM_MEMBERS_TEXT = "В твоей команде пока нет участников для отчёта."
CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT = "Этот участник не из твоей команды."
CAPTAIN_DROPPED_PARTICIPANT_TEXT = "За выбывшего участника нельзя внести отчёт."
CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT = "Отчёт за этого участника уже принят на этой неделе."
CAPTAIN_MANUAL_REPORT_LATE_TEXT = "Дедлайн недели уже прошёл. Капитанский отчёт не может изменить статус."
CAPTAIN_EMPTY_REPORT_TEXT = "Отправь текст отчёта за участника, потом нажми «✅ Готово»."
CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT = "Капитанский отчёт сохранён."

INSIGHT_ADD_BUTTON = "➕ Добавить инсайт"
INSIGHT_LIST_BUTTON = "📜 Посмотреть инсайты"
INSIGHT_CANCEL_BUTTON = "Отмена"
INSIGHT_DONE_BUTTON = "✅ Готово"
INSIGHT_READ_FULL_TEXT = "читать целиком"

INSIGHT_TITLE_PROMPT_TEXT = "Как кратко озаглавить твой инсайт?"
INSIGHT_TITLE_TOO_LONG_TEXT = "Заголовок должен быть не длиннее 120 символов. Сократи его, пожалуйста."
INSIGHT_EMPTY_TEXT = "Я не получил текст инсайта. Отправь инсайт текстом и нажми ✅ Готово."
INSIGHT_EMPTY_LIST_TEXT = "У тебя пока нет сохранённых инсайтов."
INSIGHT_SUCCESS_TEXT = "Инсайт сохранён."
INSIGHT_DUPLICATE_TEXT = "Инсайт уже сохранён."
INSIGHT_MISSING_TEXT = "Инсайт не найден."
INSIGHT_MISSING_ACTIVE_GOAL_TEXT = "Прости, у тебя не зафиксировано активной цели, обратись к капитану"
INSIGHT_VOICE_NOT_AVAILABLE_TEXT = "Голосовые инсайты будут доступны позже. Сейчас отправь текст."

SCHEDULER_REMINDER_TEXTS = {
    "monday_reminder": "Новая неделя началась.\n\nПроверь свои шаги и запланируй победу недели.",
    "wednesday_checkin": "Короткий чек-ап.\n\nКак идёт движение по шагам на этой неделе?",
    "sunday_1800_checkin": "Дедлайн отчёта сегодня в 23:59 по Екатеринбургу.",
    "sunday_2230_reminder": (
        "Напоминание: отчёт за неделю ещё не отправлен.\n\n"
        "Дедлайн сегодня в 23:59 по Екатеринбургу."
    ),
    "sunday_2300_reminder": (
        "Последнее напоминание.\n\n"
        "Если отчёт не будет отправлен до 23:59 по Екатеринбургу, "
        "неделя будет отмечена как ⬜ нет ответа."
    ),
}


def format_missing_data_message() -> str:
    return MISSING_DATA_TEXT


def format_scheduler_reminder_text(reminder_type: str) -> str:
    return SCHEDULER_REMINDER_TEXTS[reminder_type]


def format_silent_participants_notification(
    *,
    week_number: int,
    participants: Sequence[object],
) -> str:
    names = [_participant_display_name(participant) for participant in participants]
    lines = [f"Нет отчёта за неделю {week_number}: {len(names)} участник(ов)."]
    lines.extend(f"- {name}" for name in names)
    return "\n".join(lines)


def build_insight_menu_buttons() -> tuple[str, str]:
    return (INSIGHT_ADD_BUTTON, INSIGHT_LIST_BUTTON)


def build_insight_text_buttons() -> tuple[str, str]:
    return (INSIGHT_DONE_BUTTON, INSIGHT_CANCEL_BUTTON)


def build_weekly_report_status_buttons() -> tuple[str, str, str]:
    return (
        WEEKLY_REPORT_GREEN_BUTTON,
        WEEKLY_REPORT_BLUE_BUTTON,
        WEEKLY_REPORT_RED_BUTTON,
    )


def format_weekly_report_status_prompt() -> str:
    return WEEKLY_REPORT_STATUS_PROMPT_TEXT


def get_weekly_report_step_required_text(status: WeeklyReportStatus) -> str:
    if status is WeeklyReportStatus.GREEN:
        return WEEKLY_REPORT_GREEN_STEP_REQUIRED_TEXT
    if status is WeeklyReportStatus.BLUE:
        return WEEKLY_REPORT_BLUE_STEP_REQUIRED_TEXT
    return ""


def get_weekly_report_success_text(status: WeeklyReportStatus) -> str:
    if status is WeeklyReportStatus.GREEN:
        return WEEKLY_REPORT_GREEN_SUCCESS_TEXT
    if status is WeeklyReportStatus.BLUE:
        return WEEKLY_REPORT_BLUE_SUCCESS_TEXT
    return WEEKLY_REPORT_RED_SUCCESS_TEXT


def format_captain_team_member_line(participant: dict[str, object]) -> str:
    name = participant.get("full_name") or participant.get("display_name") or participant.get("name")
    if isinstance(name, str) and name.strip():
        return f"• {name.strip()}"
    return "• Участник без имени"


def _participant_display_name(participant: object) -> str:
    name = getattr(participant, "full_name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()

    if isinstance(participant, dict):
        row_name = participant.get("full_name") or participant.get("display_name") or participant.get("name")
        if isinstance(row_name, str) and row_name.strip():
            return row_name.strip()

    return "Участник без имени"


def make_insight_title_fallback(text: str, *, limit: int = 100) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized

    suffix = "..."
    trimmed = normalized[: limit - len(suffix)].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return f"{trimmed}{suffix}"


def format_insight_page(page: InsightPage) -> str:
    if not page.items:
        return INSIGHT_EMPTY_LIST_TEXT

    start = page.page_index * page.page_size + 1
    end = min((page.page_index + 1) * page.page_size, page.total_count)
    lines = [f"Твои инсайты: {start}-{end} из {page.total_count}"]

    for item in page.items:
        lines.extend(
            (
                "",
                _format_insight_date(item.insight_date),
                f"Инсайт: {item.title}",
                f"{_truncate_insight_preview(item.text_preview)}...{INSIGHT_READ_FULL_TEXT}",
            )
        )

    return "\n".join(lines)


def format_full_insight_text(item: InsightListItem) -> str:
    full_text = item.full_text if item.full_text is not None else item.text_preview
    return "\n".join(
        (
            _format_insight_date(item.insight_date),
            f"Инсайт: {item.title}",
            "",
            full_text,
        )
    )


def format_goal_view(goal: Goal) -> str:
    return "\n".join(
        (
            f"Цель: {goal.goal_title}",
            f"Описание: {goal.goal_description}",
            f"Ценность: {_format_goal_value(goal)}",
            f"Условие разрешения: {goal.permission_condition}",
        )
    )


def format_planned_steps_view(steps: Sequence[PlannedStep]) -> str:
    open_steps = [step for step in sorted(steps, key=lambda item: item.step_number) if step.step_status != "closed"]
    closed_steps = [step for step in sorted(steps, key=lambda item: item.step_number) if step.step_status == "closed"]
    progress_percent = calculate_progress_percent(steps)
    lines = [f"Прогресс: {progress_percent}%"]

    if open_steps:
        lines.append("Открытые шаги:")
        lines.extend(_format_step_lines(open_steps))

    if closed_steps:
        lines.append("Закрытые шаги:")
        lines.extend(_format_step_lines(closed_steps))

    if len(lines) == 1:
        lines.append("Шаги пока не заполнены.")

    return "\n".join(lines)


def format_progress_view(
    *,
    steps: Sequence[PlannedStep],
    weekly_history: Sequence[WeeklyStatus] = (),
) -> str:
    percent = calculate_progress_percent(steps)
    lines = [
        f"Прогресс: {percent}%",
        f"Шаги: {_format_progress_bar(steps)}",
    ]

    if weekly_history:
        lines.append("История недель:")
        lines.extend(
            f"Неделя {item.week_number}: {item.status_symbol}"
            for item in sorted(weekly_history, key=lambda status: status.week_number)
        )

    return "\n".join(lines)


def calculate_progress_percent(steps: Sequence[PlannedStep]) -> int:
    if not steps:
        return 0
    closed_count = sum(1 for step in steps if step.step_status == "closed")
    return round(closed_count / len(steps) * 100)


def _format_progress_bar(steps: Sequence[PlannedStep]) -> str:
    if not steps:
        return "□□□□□□"
    closed_count = sum(1 for step in steps if step.step_status == "closed")
    filled_cells = round(closed_count / len(steps) * 6)
    return "■" * filled_cells + "□" * (6 - filled_cells)


def _format_goal_value(goal: Goal) -> str:
    amount = goal.goal_value_amount
    currency = goal.goal_value_currency
    if amount in (None, "") and not currency:
        return "не указана"
    if amount in (None, ""):
        return str(currency)
    if not currency:
        return str(amount)
    return f"{amount} {currency}"


def _format_insight_date(value: str) -> str:
    parts = value.split("-", 2)
    if len(parts) == 3 and all(parts):
        year, month, day = parts
        return f"{day}.{month}.{year}"
    return value


def _truncate_insight_preview(text: str, *, limit: int = 100) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    trimmed = normalized[:limit].rstrip()
    if " " in trimmed:
        trimmed = trimmed.rsplit(" ", 1)[0]
    return trimmed


def _format_step_lines(steps: Sequence[PlannedStep]) -> list[str]:
    return [f"{step.step_number}. {step.step_title}" for step in steps]
