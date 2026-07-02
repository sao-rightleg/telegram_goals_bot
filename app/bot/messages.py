"""Russian Telegram copy and read-only view formatters."""

from __future__ import annotations

from collections.abc import Sequence

from app.services.participant_models import Goal, PlannedStep, WeeklyStatus


UNKNOWN_USER_TEXT = "Извините, вас нет в базе участников. Свяжитесь со своим капитаном."
CONSENT_TEXT = (
    "Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору "
    "и Александру Ситникову в рамках челленджа."
)
CONSENT_ACCEPT_BUTTON = "✅ Согласен"
MISSING_DATA_TEXT = "Данные пока не заполнены. Свяжитесь со своим капитаном."
NOT_AVAILABLE_TEXT = "Раздел будет доступен позже."


def format_missing_data_message() -> str:
    return MISSING_DATA_TEXT


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


def _format_step_lines(steps: Sequence[PlannedStep]) -> list[str]:
    return [f"{step.step_number}. {step.step_title}" for step in steps]
