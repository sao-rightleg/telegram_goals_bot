"""Russian text formatters for report delivery."""

from __future__ import annotations

from app.reports.models import AllTeamsReportData, ParticipantReportSection, TeamReportData


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
        f"⬜ {distribution.get('gray', 0)}"
    )


def _join_items(items: tuple[str, ...]) -> str:
    return "; ".join(item for item in items if item)
