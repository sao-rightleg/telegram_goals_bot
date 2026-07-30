"""Build report-ready data from final Sheets facts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from app.reports.models import AllTeamsReportData, ParticipantReportSection, TeamReportData
from app.sheets.gateway import SheetsGateway, SheetRow


STATUS_CODES = ("green", "blue", "red", "gray")
STATUS_SYMBOLS = {
    "green": "🟩",
    "blue": "🟦",
    "red": "🟥",
    "gray": "⬜",
}
STATUS_SCORES = {
    "green": 1.0,
    "blue": 0.5,
    "red": 0.0,
    "gray": 0.0,
}
STEP_SYMBOLS = {
    "closed": "🟩",
    "partial": "🟦",
}


def build_all_teams_report(gateway: SheetsGateway, *, week_number: int) -> AllTeamsReportData:
    teams = gateway.list_teams()
    participants = gateway.list_participants()
    goals = gateway.list_goals()
    planned_steps = gateway.list_planned_steps_all()
    weekly_reports = gateway.list_weekly_reports_for_week(week_number)
    weekly_focus = gateway.list_weekly_focus_for_week(week_number)
    insights = gateway.list_insights_for_week(week_number)

    participants_by_team = _group_by(participants, "team_id")
    participants_by_id = {str(row.get("participant_id")): row for row in participants}
    goals_by_participant = _group_by(goals, "participant_id")
    steps_by_participant = _group_by(planned_steps, "participant_id")
    reports_by_participant = {str(row.get("participant_id")): row for row in weekly_reports}
    focus_by_participant = {str(row.get("participant_id")): row for row in weekly_focus}
    insights_by_participant = _group_by(insights, "participant_id")

    team_reports = tuple(
        _build_team_report(
            team=team,
            participants=participants_by_team.get(str(team.get("team_id")), []),
            participants_by_id=participants_by_id,
            goals_by_participant=goals_by_participant,
            steps_by_participant=steps_by_participant,
            reports_by_participant=reports_by_participant,
            focus_by_participant=focus_by_participant,
            insights_by_participant=insights_by_participant,
            week_number=week_number,
        )
        for team in teams
    )
    total_active_count = sum(team.active_count for team in team_reports)
    total_dropped_count = sum(team.dropped_count for team in team_reports)
    average_victory_percent = _average(
        [team.weekly_victory_percent for team in team_reports if team.active_count > 0]
    )
    return AllTeamsReportData(
        week_number=week_number,
        teams=team_reports,
        total_active_count=total_active_count,
        total_dropped_count=total_dropped_count,
        average_victory_percent=average_victory_percent,
    )


def _build_team_report(
    *,
    team: SheetRow,
    participants: list[SheetRow],
    participants_by_id: dict[str, SheetRow],
    goals_by_participant: dict[str, list[SheetRow]],
    steps_by_participant: dict[str, list[SheetRow]],
    reports_by_participant: dict[str, SheetRow],
    focus_by_participant: dict[str, SheetRow],
    insights_by_participant: dict[str, list[SheetRow]],
    week_number: int,
) -> TeamReportData:
    participant_sections = tuple(
        _build_participant_section(
            participant=participant,
            goals=goals_by_participant.get(str(participant.get("participant_id")), []),
            steps=steps_by_participant.get(str(participant.get("participant_id")), []),
            weekly_report=reports_by_participant.get(str(participant.get("participant_id"))),
            weekly_focus=focus_by_participant.get(str(participant.get("participant_id"))),
            insights=insights_by_participant.get(str(participant.get("participant_id")), []),
        )
        for participant in participants
        if participant.get("role") != "captain"
    )
    active_sections = [section for section in participant_sections if not section.is_dropped]
    status_distribution = {code: 0 for code in STATUS_CODES}
    for section in participant_sections:
        status_distribution[_status_code_from_symbol(section.status)] += 1

    captain = participants_by_id.get(str(team.get("captain_id")), {})
    return TeamReportData(
        week_number=week_number,
        team_id=str(team.get("team_id", "")),
        team_name=str(team.get("team_name") or team.get("name") or "Команда без названия"),
        captain_id=_optional_str(team.get("captain_id")),
        captain_name=str(captain.get("full_name") or "Капитан не указан"),
        active_count=len(active_sections),
        dropped_count=len(participant_sections) - len(active_sections),
        status_distribution=status_distribution,
        weekly_victory_percent=_weekly_victory_percent(active_sections),
        participants=participant_sections,
    )


def _build_participant_section(
    *,
    participant: SheetRow,
    goals: list[SheetRow],
    steps: list[SheetRow],
    weekly_report: SheetRow | None,
    weekly_focus: SheetRow | None,
    insights: list[SheetRow],
) -> ParticipantReportSection:
    goal = _active_goal(goals)
    sorted_steps = sorted(steps, key=lambda row: int(row.get("step_number") or 0))
    status_code = _weekly_status_code(weekly_report)
    return ParticipantReportSection(
        participant_id=str(participant.get("participant_id", "")),
        team_id=str(participant.get("team_id", "")),
        full_name=str(participant.get("full_name") or "Участник без имени"),
        username=_optional_str(participant.get("username")),
        status=STATUS_SYMBOLS[status_code],
        is_dropped=participant.get("status") == "dropped",
        risk_state=_risk_state(participant),
        progress_bar=_progress_bar(sorted_steps),
        progress_percent=_progress_percent(sorted_steps),
        goal_title=str(goal.get("goal_title") or "Цель не указана"),
        goal_description=str(goal.get("goal_description") or ""),
        goal_value=_goal_value(goal),
        permission_condition=str(goal.get("permission_condition") or ""),
        planned_steps=tuple(str(row.get("step_title") or "") for row in sorted_steps),
        completed_steps=tuple(
            str(row.get("step_title") or "")
            for row in sorted_steps
            if row.get("step_status") == "closed"
        ),
        partial_steps=tuple(
            str(row.get("step_title") or "")
            for row in sorted_steps
            if row.get("step_status") == "partial"
        ),
        weekly_focus_step=_focus_step_title(sorted_steps, weekly_focus),
        report_text=_optional_str(weekly_report.get("report_text")) if weekly_report else None,
        transcription_text=_optional_str(weekly_report.get("transcription_text")) if weekly_report else None,
        insights=tuple(_insight_text(row) for row in insights if _insight_text(row)),
    )


def _group_by(rows: Iterable[SheetRow], key: str) -> dict[str, list[SheetRow]]:
    grouped: dict[str, list[SheetRow]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value is not None:
            grouped[str(value)].append(row)
    return dict(grouped)


def _active_goal(goals: list[SheetRow]) -> SheetRow:
    for goal in goals:
        if goal.get("goal_status") == "active":
            return goal
    return goals[0] if goals else {}


def _weekly_status_code(weekly_report: SheetRow | None) -> str:
    if weekly_report is None:
        return "gray"
    code = str(weekly_report.get("status_code") or "gray")
    return code if code in STATUS_CODES else "gray"


def _status_code_from_symbol(symbol: str) -> str:
    for code, candidate in STATUS_SYMBOLS.items():
        if candidate == symbol:
            return code
    return "gray"


def _weekly_victory_percent(active_sections: list[ParticipantReportSection]) -> int:
    if not active_sections:
        return 0
    total = sum(STATUS_SCORES[_status_code_from_symbol(section.status)] for section in active_sections)
    return round(total / len(active_sections) * 100)


def _progress_percent(steps: list[SheetRow]) -> int:
    if not steps:
        return 0
    score = sum(_step_score(step) for step in steps)
    return round(score / 6 * 100)


def _progress_bar(steps: list[SheetRow]) -> str:
    symbols = [STEP_SYMBOLS.get(str(step.get("step_status")), "⬜") for step in steps[:6]]
    return "".join(symbols + ["⬜"] * (6 - len(symbols)))


def _step_score(step: SheetRow) -> float:
    status = step.get("step_status")
    if status == "closed":
        return 1.0
    if status == "partial":
        return 0.5
    return 0.0


def _risk_state(participant: SheetRow) -> str:
    status = participant.get("status")
    if status == "dropped":
        return "dropped"
    if status == "risk_zone":
        return "risk_zone"
    return "ok"


def _goal_value(goal: SheetRow) -> str:
    amount = goal.get("goal_value_amount")
    currency = goal.get("goal_value_currency")
    if amount in (None, "") and not currency:
        return "не указана"
    if amount in (None, ""):
        return str(currency)
    if not currency:
        return str(amount)
    return f"{amount} {currency}"


def _insight_text(row: SheetRow) -> str:
    return str(row.get("insight_text") or row.get("text") or "")


def _focus_step_title(steps: list[SheetRow], weekly_focus: SheetRow | None) -> str | None:
    if weekly_focus is None:
        return None
    focus_step_id = weekly_focus.get("step_id")
    for step in steps:
        if step.get("step_id") == focus_step_id:
            return _optional_str(step.get("step_title"))
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _average(values: list[int]) -> int:
    if not values:
        return 0
    return round(sum(values) / len(values))
