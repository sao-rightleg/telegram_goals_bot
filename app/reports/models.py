"""Adapter-independent report data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ReportType(str, Enum):
    TELEGRAM_TEAM_SUMMARY = "telegram_team_summary"
    TELEGRAM_TRACKER_SUMMARY = "telegram_tracker_summary"
    TELEGRAM_ADMIN_SUMMARY = "telegram_admin_summary"
    TELEGRAM_SITNIKOV_SUMMARY = "telegram_sitnikov_summary"
    PDF_TEAM_REPORT = "pdf_team_report"
    PDF_TRACKER_REPORT = "pdf_tracker_report"
    PDF_FULL_REPORT = "pdf_full_report"
    FULL_SUMMARY = "full_summary"
    GROUP_COMPARISON = "group_comparison"


@dataclass(frozen=True)
class ParticipantReportSection:
    participant_id: str
    team_id: str
    full_name: str
    username: str | None
    status: str
    is_dropped: bool
    risk_state: str
    progress_bar: str
    progress_percent: int
    goal_title: str
    goal_description: str
    goal_value: str
    permission_condition: str
    planned_steps: tuple[str, ...] = field(default_factory=tuple)
    completed_steps: tuple[str, ...] = field(default_factory=tuple)
    partial_steps: tuple[str, ...] = field(default_factory=tuple)
    weekly_focus_step: str | None = None
    report_text: str | None = None
    transcription_text: str | None = None
    insights: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TeamReportData:
    week_number: int
    team_id: str
    team_name: str
    captain_id: str | None
    captain_name: str
    active_count: int
    dropped_count: int
    status_distribution: dict[str, int]
    weekly_victory_percent: int
    participants: tuple[ParticipantReportSection, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AllTeamsReportData:
    week_number: int
    teams: tuple[TeamReportData, ...]
    total_active_count: int
    total_dropped_count: int
    average_victory_percent: int


@dataclass(frozen=True)
class ReportRecipient:
    recipient_type: str
    recipient_id: str
    chat_id: str
    team_scope_id: str | None = None


@dataclass(frozen=True)
class ReportDeliveryItem:
    report_type: ReportType
    scope_id: str
    recipient: ReportRecipient
    text: str | None = None
    file_path: Path | None = None


@dataclass(frozen=True)
class ReportRunResult:
    generated_count: int
    sent_count: int
    skipped_count: int
    failed_count: int
