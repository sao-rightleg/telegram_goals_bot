"""Role-safe report delivery planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.reports.models import AllTeamsReportData, ReportDeliveryItem, ReportRecipient, ReportType, TeamReportData
from app.sheets.gateway import SheetRow


@dataclass(frozen=True)
class ReportDeliveryProblem:
    reason: str
    recipient_type: str
    recipient_id: str
    scope_id: str


@dataclass(frozen=True)
class ReportDeliveryPlan:
    items: list[ReportDeliveryItem] = field(default_factory=list)
    problems: list[ReportDeliveryProblem] = field(default_factory=list)


@dataclass(frozen=True)
class ReportDeliveryPlanner:
    team_summary_texts: dict[str, str]
    team_pdf_paths: dict[str, Path]
    full_summary_text: str
    group_comparison_text: str

    def build_plan(
        self,
        report: AllTeamsReportData,
        *,
        participants: list[SheetRow],
        teams: list[SheetRow],
        trackers: list[SheetRow],
    ) -> ReportDeliveryPlan:
        items: list[ReportDeliveryItem] = []
        problems: list[ReportDeliveryProblem] = []
        participants_by_id = {str(row.get("participant_id")): row for row in participants}
        team_rows_by_id = {str(row.get("team_id")): row for row in teams}

        for team in report.teams:
            captain_id = team.captain_id or str(team_rows_by_id.get(team.team_id, {}).get("captain_id") or "")
            captain = participants_by_id.get(captain_id)
            self._append_team_items(
                items=items,
                problems=problems,
                team=team,
                recipient_type="captain",
                recipient_id=captain_id,
                chat_id=_chat_id(captain),
            )

        for tracker in trackers:
            if not _is_active(tracker):
                continue
            tracker_id = str(tracker.get("tracker_id") or "")
            for team in report.teams:
                if not _tracker_can_receive_team(tracker, team_rows_by_id.get(team.team_id, {})):
                    continue
                self._append_team_items(
                    items=items,
                    problems=problems,
                    team=team,
                    recipient_type="tracker",
                    recipient_id=tracker_id,
                    chat_id=_chat_id(tracker),
                )

        for participant in participants:
            role = participant.get("role")
            if role == "admin":
                self._append_global_items(
                    items=items,
                    problems=problems,
                    report=report,
                    recipient_type="admin",
                    recipient_id=str(participant.get("participant_id") or ""),
                    chat_id=_chat_id(participant),
                )
            if role == "sitnikov":
                self._append_global_items(
                    items=items,
                    problems=problems,
                    report=report,
                    recipient_type="sitnikov",
                    recipient_id=str(participant.get("participant_id") or ""),
                    chat_id=_chat_id(participant),
                )

        return ReportDeliveryPlan(items=items, problems=problems)

    def _append_global_items(
        self,
        *,
        items: list[ReportDeliveryItem],
        problems: list[ReportDeliveryProblem],
        report: AllTeamsReportData,
        recipient_type: str,
        recipient_id: str,
        chat_id: str | None,
    ) -> None:
        for team in report.teams:
            self._append_team_items(
                items=items,
                problems=problems,
                team=team,
                recipient_type=recipient_type,
                recipient_id=recipient_id,
                chat_id=chat_id,
            )
        recipient = self._recipient_or_problem(
            problems=problems,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            chat_id=chat_id,
            scope_id="global",
        )
        if recipient is None:
            return
        items.extend(
            [
                ReportDeliveryItem(
                    report_type=ReportType.FULL_SUMMARY,
                    scope_id="global",
                    recipient=recipient,
                    text=self.full_summary_text,
                ),
                ReportDeliveryItem(
                    report_type=ReportType.GROUP_COMPARISON,
                    scope_id="global",
                    recipient=recipient,
                    text=self.group_comparison_text,
                ),
            ]
        )

    def _append_team_items(
        self,
        *,
        items: list[ReportDeliveryItem],
        problems: list[ReportDeliveryProblem],
        team: TeamReportData,
        recipient_type: str,
        recipient_id: str,
        chat_id: str | None,
    ) -> None:
        recipient = self._recipient_or_problem(
            problems=problems,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            chat_id=chat_id,
            scope_id=team.team_id,
        )
        if recipient is None:
            return
        items.extend(
            [
                ReportDeliveryItem(
                    report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                    scope_id=team.team_id,
                    recipient=recipient,
                    text=self.team_summary_texts[team.team_id],
                ),
                ReportDeliveryItem(
                    report_type=ReportType.PDF_TEAM_REPORT,
                    scope_id=team.team_id,
                    recipient=recipient,
                    file_path=self.team_pdf_paths[team.team_id],
                ),
            ]
        )

    def _recipient_or_problem(
        self,
        *,
        problems: list[ReportDeliveryProblem],
        recipient_type: str,
        recipient_id: str,
        chat_id: str | None,
        scope_id: str,
    ) -> ReportRecipient | None:
        if not chat_id:
            problems.append(
                ReportDeliveryProblem(
                    reason="missing_chat_id",
                    recipient_type=recipient_type,
                    recipient_id=recipient_id,
                    scope_id=scope_id,
                )
            )
            return None
        return ReportRecipient(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            chat_id=chat_id,
            team_scope_id=None if scope_id == "global" else scope_id,
        )


def _chat_id(row: SheetRow | None) -> str | None:
    if not row:
        return None
    value = row.get("chat_id") or row.get("telegram_id")
    return str(value) if value not in (None, "") else None


def _is_active(row: SheetRow) -> bool:
    value = row.get("is_active")
    return value is not False and value != "false"


def _tracker_can_receive_team(tracker: SheetRow, team: SheetRow) -> bool:
    tracker_id = tracker.get("tracker_id")
    if team.get("tracker_id") and team.get("tracker_id") == tracker_id:
        return True
    scope = tracker.get("gender_scope")
    return scope == "all" or (scope is not None and scope == team.get("gender"))
