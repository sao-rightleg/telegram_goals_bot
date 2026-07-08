"""Report generation boundary and fake implementation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from app.reports.models import TeamReportData
from app.reports.pdf import LocalPdfRenderer
from app.storage.paths import StoragePathPolicy


class ReportType(str, Enum):
    TELEGRAM_TEAM_SUMMARY = "telegram_team_summary"
    PDF_TEAM_REPORT = "pdf_team_report"
    FULL_ADMIN_SUMMARY = "full_admin_summary"
    SITNIKOV_SUMMARY = "sitnikov_summary"


@dataclass(frozen=True)
class ReportRequest:
    report_type: ReportType
    week_number: int
    team_id: str
    year: int = 2026
    team_report: TeamReportData | None = None


@dataclass(frozen=True)
class GeneratedReport:
    report_type: ReportType
    file_path: Path | None
    text: str | None = None


class ReportGenerator(Protocol):
    def generate_team_report(self, request: ReportRequest) -> GeneratedReport:
        """Generate a report through a concrete report implementation."""


@dataclass(frozen=True)
class LocalReportGenerator:
    pdf_renderer: LocalPdfRenderer

    def generate_team_report(self, request: ReportRequest) -> GeneratedReport:
        if request.report_type is ReportType.PDF_TEAM_REPORT:
            if request.team_report is None:
                raise ValueError("team_report is required for PDF team reports")
            rendered = self.pdf_renderer.render_team_report(request.team_report, year=request.year)
            return GeneratedReport(report_type=request.report_type, file_path=rendered.file_path)
        return GeneratedReport(
            report_type=request.report_type,
            file_path=None,
            text=f"Report {request.report_type.value} for {request.team_id}",
        )


@dataclass(frozen=True)
class FakeReportGenerator:
    path_policy: StoragePathPolicy

    def generate_team_report(self, request: ReportRequest) -> GeneratedReport:
        if request.report_type is ReportType.PDF_TEAM_REPORT:
            path = self.path_policy.pdf_path(
                year=request.year,
                week_number=request.week_number,
                team_slug=request.team_id,
                file_name=f"{request.team_id}.pdf",
            )
            return GeneratedReport(report_type=request.report_type, file_path=path)
        return GeneratedReport(
            report_type=request.report_type,
            file_path=None,
            text=f"Report {request.report_type.value} for {request.team_id}",
        )
