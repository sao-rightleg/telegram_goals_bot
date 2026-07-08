"""High-level weekly report generation and delivery orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.reports.aggregation import build_all_teams_report
from app.reports.delivery import ReportDeliveryPlanner, ReportDeliveryService
from app.reports.formatting import (
    format_full_summary_text,
    format_group_comparison_text,
    format_team_summary_text,
)
from app.reports.models import ReportRunResult
from app.reports.pdf import LocalPdfRenderer
from app.sheets.gateway import SheetsGateway
from app.storage.reports import ReportStateRepository


@dataclass(frozen=True)
class ReportService:
    sheets_gateway: SheetsGateway
    report_repository: ReportStateRepository
    pdf_renderer: LocalPdfRenderer
    delivery_service: ReportDeliveryService
    year: int = 2026

    def generate_and_send_week(self, week_number: int, *, now: datetime) -> ReportRunResult:
        started_at = now.isoformat()
        run_id = self.report_repository.start_job_run(
            week_number=week_number,
            idempotency_key=f"reports:week_{week_number:02d}",
            started_at=started_at,
        )
        try:
            report = build_all_teams_report(self.sheets_gateway, week_number=week_number)
            team_summary_texts = {
                team.team_id: format_team_summary_text(team)
                for team in report.teams
            }
            team_pdf_paths = {}
            pdf_failure_count = 0
            for team in report.teams:
                try:
                    team_pdf_paths[team.team_id] = self.pdf_renderer.render_team_report(
                        team,
                        year=self.year,
                    ).file_path
                except Exception as exc:  # noqa: BLE001 - per-team PDF failure must not block reports.
                    pdf_failure_count += 1
                    self.delivery_service._notify_admin(
                        "report_pdf_generation_failed",
                        (
                            "report_pdf_generation_failed "
                            f"week_number={week_number} team_id={team.team_id} "
                            f"error={_safe_service_error(str(exc))}"
                        ),
                    )

            planner = ReportDeliveryPlanner(
                team_summary_texts=team_summary_texts,
                team_pdf_paths=team_pdf_paths,
                full_summary_text=format_full_summary_text(report),
                group_comparison_text=format_group_comparison_text(report),
            )
            plan = planner.build_plan(
                report,
                participants=self.sheets_gateway.list_participants(),
                teams=self.sheets_gateway.list_teams(),
                trackers=self.sheets_gateway.list_trackers() if hasattr(self.sheets_gateway, "list_trackers") else [],
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
                failed_count=delivery_result.failed_count + pdf_failure_count,
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


def _safe_service_error(message: str) -> str:
    return " ".join(message.split()).replace("token=", "redacted=")[:240]
