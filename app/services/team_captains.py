"""Authoritative team-to-captain assignment helpers."""

from __future__ import annotations

from app.sheets.gateway import SheetRow, SheetsGateway


def list_team_captain_assignments(
    sheets: SheetsGateway, *, teams: list[SheetRow] | None = None,
    default_flow_id: str | None = None,
) -> list[SheetRow]:
    """Return explicit assignments, falling back to legacy Teams columns."""
    explicit = sheets.list_team_captains()
    team_rows = teams if teams is not None else sheets.list_teams()
    configured_teams = {
        (str(row.get("flow_id") or ""), str(row.get("team_id") or ""))
        for row in explicit
    }
    legacy = [
        {
            "flow_id": team.get("flow_id") or default_flow_id or "",
            "team_id": team.get("team_id", ""),
            "captain_id": team.get("captain_id", ""),
            "captain_telegram_id": team.get("captain_telegram_id", ""),
            "is_primary": True,
            "is_active": team.get("is_active", True) is not False,
            "_assignment_source": "legacy_teams",
        }
        for team in team_rows
        if team.get("captain_id")
        and (
            str(team.get("flow_id") or default_flow_id or ""),
            str(team.get("team_id") or ""),
        ) not in configured_teams
    ]
    return [*explicit, *legacy]


def active_team_captain_assignments(
    sheets: SheetsGateway,
    *,
    flow_id: str,
    team_id: str | None = None,
) -> list[SheetRow]:
    return [
        row
        for row in list_team_captain_assignments(sheets)
        if str(row.get("flow_id") or "") == flow_id
        and (team_id is None or str(row.get("team_id") or "") == team_id)
        and row.get("is_active") is True
        and str(row.get("captain_id") or "")
    ]


def primary_team_captain(
    sheets: SheetsGateway,
    *,
    flow_id: str,
    team_id: str,
) -> SheetRow | None:
    assignments = active_team_captain_assignments(
        sheets, flow_id=flow_id, team_id=team_id
    )
    primary = [row for row in assignments if row.get("is_primary") is True]
    return primary[0] if len(primary) == 1 else None
