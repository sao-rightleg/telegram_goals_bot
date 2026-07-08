"""Google Sheets boundary and fake in-memory implementation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol


SheetRow = dict[str, object]


class SheetsGateway(Protocol):
    def list_participants(self) -> list[SheetRow]:
        """Return all participant rows for scheduler selection."""

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        """Find a participant business row by Telegram ID."""

    def get_participant(self, participant_id: str) -> SheetRow | None:
        """Find a participant business row by stable participant ID."""

    def list_participants_by_team(self, team_id: str) -> list[SheetRow]:
        """Return participant rows scoped to one team."""

    def list_teams(self) -> list[SheetRow]:
        """Return team rows used to resolve captain/tracker recipients."""

    def get_tracker(self, tracker_id: str) -> SheetRow | None:
        """Return one tracker row by stable tracker ID."""

    def update_participant_consent(
        self,
        participant_id: str,
        *,
        consent_given: bool,
        consent_given_at: str,
    ) -> None:
        """Persist participant consent fields to the business storage."""

    def get_active_goal(self, participant_id: str) -> SheetRow | None:
        """Return the participant's active goal row when available."""

    def list_planned_steps(self, participant_id: str, goal_id: str) -> list[SheetRow]:
        """Return planned steps scoped to the participant and goal."""

    def list_weekly_status_history(self, participant_id: str) -> list[SheetRow]:
        """Return weekly report/status rows scoped to the participant."""

    def append_weekly_report(self, row: SheetRow) -> None:
        """Append a final weekly report row to the business storage."""

    def find_weekly_report(self, participant_id: str, *, week_number: int) -> SheetRow | None:
        """Find one weekly report for a participant/week if it already exists."""

    def append_weekly_report_step(self, row: SheetRow) -> None:
        """Append a final weekly report to planned-step relation row."""

    def close_planned_steps(
        self,
        participant_id: str,
        goal_id: str,
        step_ids: Sequence[str],
        *,
        closed_week_number: int,
        closed_report_id: str,
        closed_at: str,
    ) -> None:
        """Mark selected participant planned steps as closed in business storage."""

    def append_insight(self, row: SheetRow) -> None:
        """Append a final insight row to the business storage."""

    def list_insights_for_participant(self, participant_id: str) -> list[SheetRow]:
        """Return final insight rows scoped to one participant."""

    def get_participant_insight(self, participant_id: str, insight_id: str) -> SheetRow | None:
        """Return one participant-scoped insight row when available."""

    def list_weekly_reports(self) -> list[SheetRow]:
        """Return weekly report rows for tests or future readers."""

    def list_weekly_report_steps(self) -> list[SheetRow]:
        """Return weekly report step relation rows for tests or future readers."""

    def list_insights(self) -> list[SheetRow]:
        """Return insight rows for tests or future readers."""

    def list_goals(self) -> list[SheetRow]:
        """Return all goal rows for report aggregation."""

    def list_planned_steps_all(self) -> list[SheetRow]:
        """Return all planned step rows for report aggregation."""

    def list_weekly_reports_for_week(self, week_number: int) -> list[SheetRow]:
        """Return final weekly report rows for one week."""

    def list_weekly_report_steps_all(self) -> list[SheetRow]:
        """Return all weekly report step relation rows for report aggregation."""

    def list_insights_for_week(self, week_number: int) -> list[SheetRow]:
        """Return final insight rows for one week."""


class FakeSheetsGateway:
    def __init__(
        self,
        *,
        participants: Iterable[SheetRow] = (),
        teams: Iterable[SheetRow] = (),
        trackers: Iterable[SheetRow] = (),
        goals: Iterable[SheetRow] = (),
        planned_steps: Iterable[SheetRow] = (),
        weekly_reports: Iterable[SheetRow] = (),
        weekly_report_steps: Iterable[SheetRow] = (),
        insights: Iterable[SheetRow] = (),
    ) -> None:
        self._participants = _copy_rows(participants)
        self._teams = _copy_rows(teams)
        self._trackers = _copy_rows(trackers)
        self._goals = _copy_rows(goals)
        self._planned_steps = _copy_rows(planned_steps)
        self._weekly_reports = _copy_rows(weekly_reports)
        self._weekly_report_steps = _copy_rows(weekly_report_steps)
        self._insights = _copy_rows(insights)

    def list_participants(self) -> list[SheetRow]:
        return [dict(row) for row in self._participants]

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        for row in self._participants:
            if row.get("telegram_id") == telegram_id:
                return dict(row)
        return None

    def get_participant(self, participant_id: str) -> SheetRow | None:
        for row in self._participants:
            if row.get("participant_id") == participant_id:
                return dict(row)
        return None

    def list_participants_by_team(self, team_id: str) -> list[SheetRow]:
        return [dict(row) for row in self._participants if row.get("team_id") == team_id]

    def list_teams(self) -> list[SheetRow]:
        return [dict(row) for row in self._teams]

    def get_tracker(self, tracker_id: str) -> SheetRow | None:
        for row in self._trackers:
            if row.get("tracker_id") == tracker_id:
                return dict(row)
        return None

    def update_participant_consent(
        self,
        participant_id: str,
        *,
        consent_given: bool,
        consent_given_at: str,
    ) -> None:
        for row in self._participants:
            if row.get("participant_id") == participant_id:
                row["consent_given"] = consent_given
                row["consent_given_at"] = consent_given_at
                return
        raise KeyError(f"Participant not found: {participant_id}")

    def get_active_goal(self, participant_id: str) -> SheetRow | None:
        for row in self._goals:
            if row.get("participant_id") == participant_id and row.get("goal_status") == "active":
                return dict(row)
        return None

    def list_planned_steps(self, participant_id: str, goal_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._planned_steps
            if row.get("participant_id") == participant_id and row.get("goal_id") == goal_id
        ]

    def list_weekly_status_history(self, participant_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._weekly_reports
            if row.get("participant_id") == participant_id
        ]

    def append_weekly_report(self, row: SheetRow) -> None:
        self._weekly_reports.append(dict(row))

    def find_weekly_report(self, participant_id: str, *, week_number: int) -> SheetRow | None:
        for row in self._weekly_reports:
            if row.get("participant_id") == participant_id and row.get("week_number") == week_number:
                return dict(row)
        return None

    def append_weekly_report_step(self, row: SheetRow) -> None:
        self._weekly_report_steps.append(dict(row))

    def close_planned_steps(
        self,
        participant_id: str,
        goal_id: str,
        step_ids: Sequence[str],
        *,
        closed_week_number: int,
        closed_report_id: str,
        closed_at: str,
    ) -> None:
        matching_rows = [
            row
            for row in self._planned_steps
            if row.get("participant_id") == participant_id
            and row.get("goal_id") == goal_id
            and row.get("step_id") in step_ids
        ]
        found_step_ids = {str(row.get("step_id")) for row in matching_rows}
        missing_step_ids = [step_id for step_id in step_ids if step_id not in found_step_ids]
        if missing_step_ids:
            raise KeyError(f"Planned steps not found for participant/goal: {', '.join(missing_step_ids)}")

        for row in matching_rows:
            row["step_status"] = "closed"
            row["closed_week_number"] = closed_week_number
            row["closed_report_id"] = closed_report_id
            row["closed_at"] = closed_at

    def append_insight(self, row: SheetRow) -> None:
        self._insights.append(dict(row))

    def list_insights_for_participant(self, participant_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._insights
            if row.get("participant_id") == participant_id
        ]

    def get_participant_insight(self, participant_id: str, insight_id: str) -> SheetRow | None:
        for row in self._insights:
            if row.get("participant_id") == participant_id and row.get("insight_id") == insight_id:
                return dict(row)
        return None

    def list_weekly_reports(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_reports]

    def list_weekly_report_steps(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_report_steps]

    def list_insights(self) -> list[SheetRow]:
        return [dict(row) for row in self._insights]

    def list_goals(self) -> list[SheetRow]:
        return [dict(row) for row in self._goals]

    def list_planned_steps_all(self) -> list[SheetRow]:
        return [dict(row) for row in self._planned_steps]

    def list_weekly_reports_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._weekly_reports
            if row.get("week_number") == week_number
        ]

    def list_weekly_report_steps_all(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_report_steps]

    def list_insights_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._insights
            if row.get("week_number") == week_number
        ]


def _copy_rows(rows: Iterable[SheetRow]) -> list[SheetRow]:
    return [dict(row) for row in rows]
