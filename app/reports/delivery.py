"""Role-safe report delivery planning."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.reports.models import AllTeamsReportData, ReportDeliveryItem, ReportRecipient, ReportType, TeamReportData
from app.services.notifications import (
    NotificationCategory,
    NotificationRouter,
    Recipient as NotificationRecipient,
    RecipientType,
)
from app.sheets.gateway import SheetRow
from app.storage.reports import ReportStateRepository


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
    tracker_pdf_paths: dict[str, Path] = field(default_factory=dict)
    full_pdf_path: Path | None = None
    flow_id: str | None = None
    tracker_summary_texts: dict[str, str] = field(default_factory=dict)
    admin_summary_text: str | None = None
    sitnikov_summary_text: str | None = None

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
        self._append_captain_reports(items, problems, report, participants_by_id, team_rows_by_id)
        self._append_tracker_reports(items, problems, trackers)
        self._append_global_reports(items, problems, participants)
        return ReportDeliveryPlan(items=items, problems=problems)

    def _append_captain_reports(
        self, items: list[ReportDeliveryItem], problems: list[ReportDeliveryProblem],
        report: AllTeamsReportData, participants_by_id: dict[str, SheetRow],
        team_rows_by_id: dict[str, SheetRow],
    ) -> None:
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

    def _append_tracker_reports(
        self, items: list[ReportDeliveryItem], problems: list[ReportDeliveryProblem],
        trackers: list[SheetRow],
    ) -> None:
        for tracker in trackers:
            if not _is_active(tracker):
                continue
            tracker_id = str(tracker.get("tracker_id") or "")
            self._append_role_text(
                items=items, problems=problems,
                report_type=ReportType.TELEGRAM_TRACKER_SUMMARY,
                text=self.tracker_summary_texts.get(tracker_id),
                recipient_type="tracker", recipient_id=tracker_id,
                chat_id=_chat_id(tracker), scope_id=self._scope(f"tracker:{tracker_id}"),
            )
            self._append_role_pdf(
                items=items,
                problems=problems,
                report_type=ReportType.PDF_TRACKER_REPORT,
                path=self.tracker_pdf_paths.get(tracker_id),
                recipient_type="tracker",
                recipient_id=tracker_id,
                chat_id=_chat_id(tracker),
                scope_id=self._scope(f"tracker:{tracker_id}"),
            )

    def _append_global_reports(
        self, items: list[ReportDeliveryItem], problems: list[ReportDeliveryProblem],
        participants: list[SheetRow],
    ) -> None:
        for participant in participants:
            role = participant.get("role")
            if role == "admin":
                self._append_global_items(items=items, problems=problems, recipient_type="admin",
                    recipient_id=str(participant.get("participant_id") or ""), chat_id=_chat_id(participant),
                    report_type=ReportType.TELEGRAM_ADMIN_SUMMARY, text=self.admin_summary_text)
            if role == "sitnikov":
                self._append_global_items(items=items, problems=problems, recipient_type="sitnikov",
                    recipient_id=str(participant.get("participant_id") or ""), chat_id=_chat_id(participant),
                    report_type=ReportType.TELEGRAM_SITNIKOV_SUMMARY, text=self.sitnikov_summary_text)

    def _append_global_items(
        self,
        *,
        items: list[ReportDeliveryItem],
        problems: list[ReportDeliveryProblem],
        recipient_type: str,
        recipient_id: str,
        chat_id: str | None,
        report_type: ReportType,
        text: str | None,
    ) -> None:
        self._append_role_text(
            items=items, problems=problems, report_type=report_type, text=text,
            recipient_type=recipient_type, recipient_id=recipient_id, chat_id=chat_id,
            scope_id=self._scope("global"),
        )
        self._append_role_pdf(
            items=items,
            problems=problems,
            report_type=ReportType.PDF_FULL_REPORT,
            path=self.full_pdf_path,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            chat_id=chat_id,
            scope_id=self._scope("global"),
        )

    def _append_role_text(
        self, *, items: list[ReportDeliveryItem], problems: list[ReportDeliveryProblem],
        report_type: ReportType, text: str | None, recipient_type: str,
        recipient_id: str, chat_id: str | None, scope_id: str,
    ) -> None:
        recipient = self._recipient_or_problem(
            problems=problems, recipient_type=recipient_type, recipient_id=recipient_id,
            chat_id=chat_id, scope_id=scope_id,
        )
        if recipient is None:
            return
        if text is None:
            problems.append(ReportDeliveryProblem("missing_text", recipient_type, recipient_id, scope_id))
            return
        items.append(ReportDeliveryItem(report_type, scope_id, recipient, text=text))

    def _append_role_pdf(
        self,
        *,
        items: list[ReportDeliveryItem],
        problems: list[ReportDeliveryProblem],
        report_type: ReportType,
        path: Path | None,
        recipient_type: str,
        recipient_id: str,
        chat_id: str | None,
        scope_id: str,
    ) -> None:
        recipient = self._recipient_or_problem(
            problems=problems,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            chat_id=chat_id,
            scope_id=scope_id,
        )
        if recipient is None:
            return
        if path is None:
            problems.append(ReportDeliveryProblem("missing_pdf", recipient_type, recipient_id, scope_id))
            return
        items.append(ReportDeliveryItem(report_type, scope_id, recipient, file_path=path))

    def _scope(self, scope_id: str) -> str:
        return scope_id if self.flow_id is None else f"{self.flow_id}:{scope_id}"

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
            scope_id=self._scope(team.team_id),
        )
        if recipient is None:
            return
        items.append(
            ReportDeliveryItem(
                report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                scope_id=self._scope(team.team_id),
                recipient=recipient,
                text=self.team_summary_texts[team.team_id],
            )
        )
        pdf_path = self.team_pdf_paths.get(team.team_id)
        if pdf_path is None:
            problems.append(
                ReportDeliveryProblem(
                    reason="missing_pdf",
                    recipient_type=recipient_type,
                    recipient_id=recipient_id,
                    scope_id=self._scope(team.team_id),
                )
            )
            return
        items.append(
            ReportDeliveryItem(
                report_type=ReportType.PDF_TEAM_REPORT,
                scope_id=self._scope(team.team_id),
                recipient=recipient,
                file_path=pdf_path,
            )
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


@dataclass(frozen=True)
class ReportDeliveryService:
    repository: ReportStateRepository
    notification_router: NotificationRouter

    def deliver_plan(
        self,
        *,
        week_number: int,
        plan: ReportDeliveryPlan,
        sent_at: str,
    ) -> "ReportRunResult":
        from app.reports.models import ReportRunResult

        failed_count = self._report_planning_problems(plan.problems)
        sent_count = skipped_count = 0
        for item in plan.items:
            outcome = self._deliver_item(week_number=week_number, item=item, sent_at=sent_at)
            sent_count += outcome == "sent"
            skipped_count += outcome == "skipped"
            failed_count += outcome == "failed"
        return ReportRunResult(
            generated_count=len(plan.items), sent_count=sent_count,
            skipped_count=skipped_count, failed_count=failed_count,
        )

    def _report_planning_problems(self, problems: list[ReportDeliveryProblem]) -> int:
        for problem in problems:
            self._notify_admin(
                "report_delivery_problem",
                (
                    f"report_delivery_problem reason={problem.reason} "
                    f"recipient_type={problem.recipient_type} "
                    f"recipient_id={problem.recipient_id} scope_id={problem.scope_id}"
                ),
            )
        return len(problems)

    def _deliver_item(self, *, week_number: int, item: ReportDeliveryItem, sent_at: str) -> str:
        identity = dict(
            week_number=week_number, report_type=item.report_type.value, scope_id=item.scope_id,
            recipient_type=item.recipient.recipient_type, recipient_id=item.recipient.recipient_id,
        )
        if self.repository.has_successful_delivery(**identity):
            return "skipped"

        try:
            self._send_item(item)
        except Exception as exc:  # noqa: BLE001 - boundary isolates Telegram failures.
            self.repository.record_delivery_attempt(
                **identity, chat_id=item.recipient.chat_id, status="failed", sent_at=sent_at,
                file_path=str(item.file_path) if item.file_path else None,
                error_message=_safe_admin_error(str(exc)),
            )
            self._notify_admin(
                "report_delivery_failed",
                f"report_delivery_failed report_type={item.report_type.value} scope_id={item.scope_id} "
                f"recipient_type={item.recipient.recipient_type} recipient_id={item.recipient.recipient_id} "
                f"error={_safe_admin_error(str(exc))}",
            )
            return "failed"
        self.repository.record_delivery_attempt(
            **identity, chat_id=item.recipient.chat_id, status="sent", sent_at=sent_at,
            file_path=str(item.file_path) if item.file_path else None,
        )
        return "sent"

    def _send_item(self, item: ReportDeliveryItem) -> None:
        recipient = NotificationRecipient(
            recipient_type=RecipientType(item.recipient.recipient_type),
            chat_id=item.recipient.chat_id,
        )
        if item.file_path is not None:
            self.notification_router.send_document(
                category=NotificationCategory.REPORT_DELIVERY,
                file_path=item.file_path,
                caption=None,
                recipients=[recipient],
            )
            return

        self.notification_router.send(
            category=NotificationCategory.REPORT_DELIVERY,
            text=item.text or "",
            recipients=[recipient],
        )

    def _notify_admin(self, error_type: str, message: str) -> None:
        self.notification_router.send(
            category=NotificationCategory.TECHNICAL_ERROR,
            text=f"{error_type}: {_safe_admin_error(message)}",
            recipients=[],
        )


def _safe_admin_error(message: str) -> str:
    compact = " ".join(message.split())
    compact = compact.replace("token=", "redacted=")
    if "личный отчёт" in compact:
        compact = compact.replace("личный отчёт", "personal_report")
    return compact[:300]
