"""Canonical report metrics derived from active participant weekly statuses."""

from __future__ import annotations

from dataclasses import dataclass

from app.reports.models import TeamReportData


@dataclass(frozen=True)
class SubmissionMetrics:
    active_count: int
    submitted_count: int
    missing_count: int

    @property
    def submitted_percent(self) -> float:
        return _percent(self.submitted_count, self.active_count)

    @property
    def missing_percent(self) -> float:
        return _percent(self.missing_count, self.active_count)


def submission_metrics(report: TeamReportData) -> SubmissionMetrics:
    """Treat green, blue, and red as submitted; only gray means no answer."""
    submitted = sum(report.status_distribution.get(code, 0) for code in ("green", "blue", "red"))
    missing = report.status_distribution.get("gray", 0)
    if submitted + missing != report.active_count:
        raise ValueError(
            "Active participant count must equal green + blue + red + gray status counts"
        )
    return SubmissionMetrics(report.active_count, submitted, missing)


def _percent(count: int, total: int) -> float:
    return 0.0 if total == 0 else round(count / total * 100, 1)
