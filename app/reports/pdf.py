"""Dependency-free local PDF renderer for MVP reports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.reports.formatting import format_participant_line, format_team_summary_text
from app.reports.models import TeamReportData
from app.storage.paths import StoragePathPolicy


@dataclass(frozen=True)
class RenderedPdfReport:
    file_path: Path


@dataclass(frozen=True)
class LocalPdfRenderer:
    path_policy: StoragePathPolicy

    def render_team_report(self, report: TeamReportData, *, year: int = 2026) -> RenderedPdfReport:
        file_path = self.path_policy.pdf_path(
            year=year,
            week_number=report.week_number,
            team_slug=report.team_id,
            file_name=f"{report.team_id}.pdf",
        )
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(_build_pdf_bytes(_team_report_text(report)))
        return RenderedPdfReport(file_path=file_path)


def _team_report_text(report: TeamReportData) -> str:
    lines = [
        "PDF Team Report",
        format_team_summary_text(report),
        "",
        "Участники:",
    ]
    for participant in report.participants:
        lines.extend(("", format_participant_line(participant)))
    return "\n".join(lines)


def _build_pdf_bytes(text: str) -> bytes:
    escaped_text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 50 780 Td ({escaped_text}) Tj ET"
    content = stream.encode("utf-8")
    return (
        b"%PDF-1.4\n"
        b"% MVP report, UTF-8 text follows for local delivery\n"
        + text.encode("utf-8")
        + b"\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        + b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        + b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        + b"/MediaBox [0 0 595 842] /Contents 5 0 R >> endobj\n"
        + b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        + f"5 0 obj << /Length {len(content)} >> stream\n".encode("ascii")
        + content
        + b"\nendstream endobj\n"
        + b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )
