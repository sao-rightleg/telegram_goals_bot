"""Google Sheets boundary and fake in-memory implementation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


SheetRow = dict[str, object]


class SheetsGateway(Protocol):
    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        """Find a participant business row by Telegram ID."""

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

    def append_insight(self, row: SheetRow) -> None:
        """Append a final insight row to the business storage."""

    def list_weekly_reports(self) -> list[SheetRow]:
        """Return weekly report rows for tests or future readers."""

    def list_insights(self) -> list[SheetRow]:
        """Return insight rows for tests or future readers."""


class FakeSheetsGateway:
    def __init__(
        self,
        *,
        participants: Iterable[SheetRow] = (),
        goals: Iterable[SheetRow] = (),
        planned_steps: Iterable[SheetRow] = (),
        weekly_reports: Iterable[SheetRow] = (),
        insights: Iterable[SheetRow] = (),
    ) -> None:
        self._participants = _copy_rows(participants)
        self._goals = _copy_rows(goals)
        self._planned_steps = _copy_rows(planned_steps)
        self._weekly_reports = _copy_rows(weekly_reports)
        self._insights = _copy_rows(insights)

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        for row in self._participants:
            if row.get("telegram_id") == telegram_id:
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

    def append_insight(self, row: SheetRow) -> None:
        self._insights.append(dict(row))

    def list_weekly_reports(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_reports]

    def list_insights(self) -> list[SheetRow]:
        return [dict(row) for row in self._insights]


def _copy_rows(rows: Iterable[SheetRow]) -> list[SheetRow]:
    return [dict(row) for row in rows]
