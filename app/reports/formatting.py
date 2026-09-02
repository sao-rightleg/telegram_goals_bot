"""Russian text formatters for report delivery."""

from __future__ import annotations

from app.reports.models import AllTeamsReportData, ParticipantReportSection, TeamReportData
from app.reports.metrics import submission_metrics


TELEGRAM_MESSAGE_LIMIT = 4096


def format_team_summary_text(report: TeamReportData) -> str:
    lines = [
        f"Неделя {report.week_number}",
        f"Команда: {report.team_name}",
        f"Капитан: {report.captain_name}",
        "",
        f"Активных: {report.active_count}",
        f"Выбывших: {report.dropped_count}",
        f"Победы недели: {report.weekly_victory_percent}%",
        _format_status_distribution(report.status_distribution),
        "",
    ]
    lines.extend(_format_participant_summary_line(participant) for participant in report.participants)
    return "\n".join(line for line in lines if line != "")


def format_captain_summary_text(report: TeamReportData) -> str:
    submitted, missing = _submission_counts(report)
    missing_names = _participant_names(report, status="⬛")
    attention = _attention_lines(report)
    lines = [
        f"📊 Итоги недели {report.week_number}",
        f"Команда «{report.team_name}»",
        "",
        f"Капитан: {report.captain_name}",
        f"Активных участников: {report.active_count}",
        f"Выбывших: {report.dropped_count}",
        "",
        "Отчётность",
        f"✅ Сдали: {_fraction(submitted, report.active_count)}",
        f"❌ Не сдали: {_fraction(missing, report.active_count)}",
        "",
        "Не сдали:",
        *_bullets_or_none(missing_names),
        "",
        "Результаты недели",
        *_status_lines(report),
        f"Победы недели: {_percent(report.weekly_victory_percent)}",
        "",
        "⚠️ Требуют внимания:",
        *(attention or ["• Нет участников, требующих внимания"]),
        "",
        "Прогресс участников",
        *(_format_participant_summary_line(item) for item in report.participants if not item.is_dropped),
        "",
        "Подробные цели, фокусные шаги, отчёты и инсайты участников — в прикреплённом PDF.",
    ]
    return _telegram_text(lines)


def format_tracker_summary_text(
    teams: tuple[TeamReportData, ...], *, tracker_name: str, week_number: int
) -> str:
    active = sum(team.active_count for team in teams)
    dropped = sum(team.dropped_count for team in teams)
    submitted = sum(_submission_counts(team)[0] for team in teams)
    missing = sum(_submission_counts(team)[1] for team in teams)
    lines = [
        f"📊 Итоги недели {week_number}",
        f"Трекер: {tracker_name}",
        f"Зона ответственности: {len(teams)} {_team_word(len(teams))}",
        "",
        f"Всего активных: {active}",
        f"✅ Сдали: {_fraction(submitted, active)}",
        f"❌ Не сдали: {_fraction(missing, active)}",
        f"Выбывших: {dropped}",
        "",
        "По командам",
    ]
    for team in teams:
        team_submitted, team_missing = _submission_counts(team)
        missing_names = _participant_names(team, status="⬛")
        lines.extend(
            [
                "",
                f"• «{team.team_name}»",
                f"Сдали: {_fraction(team_submitted, team.active_count)}",
                f"Не сдали: {_fraction(team_missing, team.active_count)}",
                f"Победы недели: {_percent(team.weekly_victory_percent)}",
                f"Не сдали участники: {', '.join(missing_names) if missing_names else 'нет'}",
            ]
        )
    lines.extend(("", "Подробные данные по закреплённым командам — в прикреплённом PDF."))
    return _telegram_text(lines)


def format_admin_summary_text(report: AllTeamsReportData, *, flow_name: str) -> str:
    lines = _global_header("Полные итоги", report, flow_name)
    lines.extend(("", "Команды с пропусками:"))
    lines.extend(_missing_team_lines(report.teams))
    lines.extend(("", "Полный отчёт по всем командам и участникам прикреплён."))
    return _telegram_text(lines)


def format_sitnikov_summary_text(report: AllTeamsReportData, *, flow_name: str) -> str:
    lines = _global_header("Итоги", report, flow_name)
    lines.extend(("", "Результаты команд"))
    for position, team in enumerate(
        sorted(report.teams, key=lambda item: item.weekly_victory_percent, reverse=True), start=1
    ):
        lines.append(f"{position}. {team.team_name} — {_percent(team.weekly_victory_percent)}")
    lines.extend(("", "Полный отчёт по командам и участникам прикреплён."))
    return _telegram_text(lines)


def format_participant_line(section: ParticipantReportSection) -> str:
    lines = [
        _format_participant_header(section),
        f"Прогресс: {section.progress_bar} {section.progress_percent}%",
        f"Цель: {section.goal_title}",
        f"Описание: {section.goal_description}",
        f"Ценность: {section.goal_value}",
        f"Условие разрешения: {section.permission_condition}",
    ]

    if section.planned_steps:
        lines.append(f"План: {_join_items(section.planned_steps)}")
    if section.completed_steps:
        lines.append(f"Сделано: {_join_items(section.completed_steps)}")
    if section.partial_steps:
        lines.append(f"Частично: {_join_items(section.partial_steps)}")
    if section.weekly_focus_step:
        lines.append(f"Фокус недели: {section.weekly_focus_step}")
    if section.report_text:
        lines.append(f"Отчёт: {section.report_text}")
    if section.transcription_text:
        lines.append(f"Расшифровка: {section.transcription_text}")
    if section.insights:
        lines.append(f"Инсайты: {_join_items(section.insights)}")

    return "\n".join(lines)


def format_full_summary_text(report: AllTeamsReportData) -> str:
    lines = [
        f"Итог недели {report.week_number}",
        f"Команд: {len(report.teams)}",
        f"Активных: {report.total_active_count}",
        f"Выбывших: {report.total_dropped_count}",
        f"Средний процент побед: {report.average_victory_percent}%",
        "",
        "Команды:",
    ]
    lines.extend(f"- {team.team_name}: {team.weekly_victory_percent}%" for team in report.teams)
    return "\n".join(line for line in lines if line != "")


def format_group_comparison_text(report: AllTeamsReportData) -> str:
    lines = [f"Сравнение групп за неделю {report.week_number}"]
    sorted_teams = sorted(report.teams, key=lambda team: team.weekly_victory_percent, reverse=True)
    lines.extend(
        (
            f"- {team.team_name} — {team.weekly_victory_percent}% "
            f"(активных {team.active_count}, выбывших {team.dropped_count})"
        )
        for team in sorted_teams
    )
    return "\n".join(lines)


def _format_participant_summary_line(section: ParticipantReportSection) -> str:
    suffix = " · выбыл" if section.is_dropped else ""
    return f"{section.full_name} — {section.progress_bar} {section.progress_percent}%{suffix}"


def _format_participant_header(section: ParticipantReportSection) -> str:
    username = f" @{section.username}" if section.username else ""
    dropped = " · выбыл" if section.is_dropped else ""
    return f"{section.full_name}{username} — {section.status}{dropped}"


def _format_status_distribution(distribution: dict[str, int]) -> str:
    return (
        "Статусы: "
        f"🟩 {distribution.get('green', 0)}, "
        f"🟦 {distribution.get('blue', 0)}, "
        f"🟥 {distribution.get('red', 0)}, "
        f"⬛ {distribution.get('gray', 0)}"
    )


def _join_items(items: tuple[str, ...]) -> str:
    return "; ".join(item for item in items if item)


def _submission_counts(report: TeamReportData) -> tuple[int, int]:
    metrics = submission_metrics(report)
    return metrics.submitted_count, metrics.missing_count


def _fraction(count: int, total: int) -> str:
    value = 0 if total == 0 else count / total * 100
    return f"{count} из {total} — {_percent(value)}"


def _percent(value: int | float) -> str:
    rounded = round(value, 1)
    text = f"{rounded:g}".replace(".", ",")
    return f"{text}%"


def _participant_names(report: TeamReportData, *, status: str) -> list[str]:
    return [item.full_name for item in report.participants if not item.is_dropped and item.status == status]


def _bullets_or_none(names: list[str]) -> list[str]:
    return [f"• {name}" for name in names] if names else ["• Нет"]


def _status_lines(report: TeamReportData) -> list[str]:
    values = report.status_distribution
    return [
        f"🟩 Победа недели: {values.get('green', 0)}",
        f"🟦 Частичная победа: {values.get('blue', 0)}",
        f"🟥 Нет победы: {values.get('red', 0)}",
        f"⬛ Нет отчёта в срок: {values.get('gray', 0)}",
    ]


def _attention_lines(report: TeamReportData) -> list[str]:
    lines: list[str] = []
    for item in report.participants:
        if item.is_dropped:
            continue
        if item.status == "⬛":
            lines.append(f"• {item.full_name} — нет отчёта в срок")
        elif item.status == "🟥":
            lines.append(f"• {item.full_name} — отчёт сдан, но победы недели нет")
        elif item.risk_state != "ok":
            lines.append(f"• {item.full_name} — зона риска")
    return lines


def _global_header(title: str, report: AllTeamsReportData, flow_name: str) -> list[str]:
    submitted = sum(_submission_counts(team)[0] for team in report.teams)
    missing = sum(_submission_counts(team)[1] for team in report.teams)
    return [
        f"📊 {title} недели {report.week_number}",
        f"Поток «{flow_name}»",
        "",
        f"Команд: {len(report.teams)}",
        f"Активных участников: {report.total_active_count}",
        f"Выбывших: {report.total_dropped_count}",
        "",
        f"✅ Сдали: {_fraction(submitted, report.total_active_count)}",
        f"❌ Не сдали: {_fraction(missing, report.total_active_count)}",
        f"Средний показатель побед: {_percent(report.average_victory_percent)}",
    ]


def _missing_team_lines(teams: tuple[TeamReportData, ...]) -> list[str]:
    ordered = sorted(teams, key=lambda team: _submission_counts(team)[1], reverse=True)
    lines = []
    for team in ordered:
        missing = _submission_counts(team)[1]
        names = _participant_names(team, status="⬛")
        lines.append(
            f"• {team.team_name} — не сдали {missing} из {team.active_count} "
            f"({_percent(0 if team.active_count == 0 else missing / team.active_count * 100)})"
        )
        if names:
            lines.append(f"  {', '.join(names)}")
    return lines


def _team_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "команда"
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return "команды"
    return "команд"


def _telegram_text(lines: list[str]) -> str:
    text = "\n".join(lines)
    if len(text) <= TELEGRAM_MESSAGE_LIMIT:
        return text
    suffix = "\n\nСписок сокращён. Полные данные находятся в прикреплённом PDF."
    available = TELEGRAM_MESSAGE_LIMIT - len(suffix)
    shortened = text[:available].rsplit("\n", 1)[0]
    return shortened + suffix
