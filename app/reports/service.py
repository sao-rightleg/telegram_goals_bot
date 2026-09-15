"""High-level weekly report generation and delivery orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.reports.aggregation import build_all_teams_report
from app.reports.delivery import ReportDeliveryPlanner, ReportDeliveryService
from app.reports.formatting import (
    format_admin_summary_text,
    format_captain_summary_text,
    format_sitnikov_summary_text,
    format_tracker_summary_text,
)
from app.reports.models import AllTeamsReportData, ReportRunResult, TeamReportData
from app.reports.pdf import LocalPdfRenderer
from app.sheets.gateway import SheetsGateway
from app.storage.reports import ReportStateRepository


@dataclass(frozen=True)
class ReportService:
    sheets_gateway: SheetsGateway
    report_repository: ReportStateRepository
    pdf_renderer: LocalPdfRenderer
    delivery_service: ReportDeliveryService
    flow_id: str
    year: int = 2026
    flow_name: str | None = None

    def generate_and_send_week(self, week_number: int, *, now: datetime) -> ReportRunResult:
        started_at = now.isoformat()
        run_id = self.report_repository.start_job_run(
            week_number=week_number,
            idempotency_key=f"reports:{self.flow_id}:week_{week_number:02d}",
            started_at=started_at,
        )
        try:
            report = build_all_teams_report(self.sheets_gateway, week_number=week_number)
            teams = self.sheets_gateway.list_teams()
            raw_trackers = self.sheets_gateway.list_trackers() if hasattr(self.sheets_gateway, "list_trackers") else []
            trackers, duplicate_tracker_ids = _unique_active_trackers(raw_trackers)
            artifacts = self._generate_pdfs(
                report, teams, trackers, duplicate_tracker_ids, week_number=week_number
            )
            planner = ReportDeliveryPlanner(
                team_summary_texts={team.team_id: format_captain_summary_text(team) for team in report.teams},
                team_pdf_paths=artifacts.team_paths,
                tracker_pdf_paths=artifacts.tracker_paths,
                full_pdf_path=artifacts.full_path,
                flow_id=self.flow_id,
                tracker_summary_texts={
                    str(tracker.get("tracker_id") or ""): format_tracker_summary_text(
                        _assigned_teams(report, teams, tracker),
                        tracker_name=str(tracker.get("full_name") or tracker.get("name") or "Трекер"),
                        week_number=week_number,
                    )
                    for tracker in trackers
                },
                admin_summary_text=format_admin_summary_text(
                    report, flow_name=self.flow_name or self.flow_id
                ),
                sitnikov_summary_text=format_sitnikov_summary_text(
                    report, flow_name=self.flow_name or self.flow_id
                ),
            )
            plan = planner.build_plan(
                report,
                participants=self.sheets_gateway.list_participants(),
                teams=teams,
                trackers=trackers,
            )
            delivery_result = self.delivery_service.deliver_plan(
                week_number=week_number,
                plan=plan,
                sent_at=started_at,
            )
            result = ReportRunResult(
                generated_count=delivery_result.generated_count,
                sent_count=delivery_result.sent_count,
                skipped_count=delivery_result.skipped_count,
                failed_count=delivery_result.failed_count + artifacts.failure_count,
            )
            status = "completed" if result.failed_count == 0 else "failed"
            self.report_repository.finish_job_run(
                run_id,
                status=status,
                finished_at=started_at,
                error_message=None if status == "completed" else "report generation completed with failures",
            )
            return result
        except Exception as exc:  # noqa: BLE001 - job lifecycle must capture unrecoverable failures.
            self.report_repository.finish_job_run(
                run_id,
                status="failed",
                finished_at=started_at,
                error_message=_safe_service_error(str(exc)),
            )
            return ReportRunResult(
                generated_count=0,
                sent_count=0,
                skipped_count=0,
                failed_count=1,
            )

    def _generate_pdfs(
        self,
        report: AllTeamsReportData,
        teams: list[dict[str, object]],
        trackers: list[dict[str, object]],
        duplicate_tracker_ids: tuple[str, ...],
        *,
        week_number: int,
    ) -> "_PdfArtifacts":
        team_paths, failures = self._generate_team_pdfs(report, week_number=week_number)
        tracker_paths, tracker_failures = self._generate_tracker_pdfs(
            report, teams, trackers, week_number=week_number
        )
        failures += tracker_failures
        for tracker_id in duplicate_tracker_ids:
            failures += 1
            self.delivery_service._notify_admin(
                "report_recipient_configuration_invalid", f"duplicate active tracker_id={tracker_id}"
            )
        full_path = None
        try:
            full_path = self.pdf_renderer.render_full_report(
                report, year=self.year, flow_id=self.flow_id
            ).file_path
        except Exception as exc:  # noqa: BLE001 - summaries must still be delivered.
            failures += 1
            self._notify_pdf_failure("full_pdf", exc)
        return _PdfArtifacts(team_paths, tracker_paths, full_path, failures)

    def _generate_team_pdfs(
        self, report: AllTeamsReportData, *, week_number: int
    ) -> tuple[dict[str, Path], int]:
        paths: dict[str, Path] = {}
        failures = 0
        for team in report.teams:
            try:
                paths[team.team_id] = self.pdf_renderer.render_team_report(
                    team, year=self.year, flow_id=self.flow_id
                ).file_path
            except Exception as exc:  # noqa: BLE001 - one team must not block other teams.
                failures += 1
                self._notify_pdf_failure(f"week_number={week_number} team_id={team.team_id}", exc)
        return paths, failures

    def _generate_tracker_pdfs(
        self,
        report: AllTeamsReportData,
        teams: list[dict[str, object]],
        trackers: list[dict[str, object]],
        *,
        week_number: int,
    ) -> tuple[dict[str, Path], int]:
        paths: dict[str, Path] = {}
        failures = 0
        for tracker in trackers:
            tracker_id = str(tracker.get("tracker_id") or "")
            assigned = _assigned_teams(report, teams, tracker)
            try:
                paths[tracker_id] = self.pdf_renderer.render_tracker_report(
                    assigned, tracker_id=tracker_id,
                    tracker_name=str(tracker.get("full_name") or tracker.get("name") or "Трекер"),
                    week_number=week_number, year=self.year, flow_id=self.flow_id,
                ).file_path
            except Exception as exc:  # noqa: BLE001 - one tracker must not block other roles.
                failures += 1
                self._notify_pdf_failure(f"tracker_id={tracker_id}", exc)
        return paths, failures

    def _notify_pdf_failure(self, scope: str, exc: Exception) -> None:
        self.delivery_service._notify_admin(
            "report_pdf_generation_failed", f"{scope} error={_safe_service_error(str(exc))}"
        )


@dataclass(frozen=True)
class _PdfArtifacts:
    team_paths: dict[str, Path]
    tracker_paths: dict[str, Path]
    full_path: Path | None
    failure_count: int


def _safe_service_error(message: str) -> str:
    return " ".join(message.split()).replace("token=", "redacted=")[:240]


def _row_is_active(row: dict[str, object]) -> bool:
    return row.get("is_active") not in (False, "false")


def _row_by_id(rows: list[dict[str, object]], key: str, value: str) -> dict[str, object]:
    return next((row for row in rows if str(row.get(key) or "") == value), {})


def _tracker_matches_team(tracker: dict[str, object], team: dict[str, object]) -> bool:
    if team.get("tracker_id") and team.get("tracker_id") == tracker.get("tracker_id"):
        return True
    scope = tracker.get("gender_scope")
    return scope == "all" or (scope is not None and scope == team.get("gender"))


def _assigned_teams(
    report: AllTeamsReportData, teams: list[dict[str, object]], tracker: dict[str, object]
) -> tuple[TeamReportData, ...]:
    return tuple(
        team for team in report.teams
        if _tracker_matches_team(tracker, _row_by_id(teams, "team_id", team.team_id))
    )


def _unique_active_trackers(
    trackers: list[dict[str, object]],
) -> tuple[list[dict[str, object]], tuple[str, ...]]:
    active = [row for row in trackers if _row_is_active(row)]
    counts: dict[str, int] = {}
    for row in active:
        tracker_id = str(row.get("tracker_id") or "")
        counts[tracker_id] = counts.get(tracker_id, 0) + 1
    duplicates = tuple(sorted(tracker_id for tracker_id, count in counts.items() if not tracker_id or count > 1))
    return [row for row in active if str(row.get("tracker_id") or "") not in duplicates], duplicates
