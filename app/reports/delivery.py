"""Role-safe report delivery planning."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from time import sleep as default_sleep
from typing import Callable

from app.bot.clients import TelegramApiError
from app.reports.models import (
    AllTeamsReportData,
    ReportDeliveryItem,
    ReportRecipient,
    ReportRunResult,
    ReportType,
    TeamReportData,
)
from app.services.notifications import (
    NotificationCategory,
    NotificationRouter,
    Recipient as NotificationRecipient,
    RecipientType,
)
from app.sheets.gateway import SheetRow
from app.services.team_captains import captain_notification_chat_id
from app.storage.reports import ReportStateRepository


@dataclass(frozen=True)
class ReportDeliveryProblem:
    reason: str
    recipient_type: str
    recipient_id: str
    scope_id: str
    report_type: str | None = None


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
        team_captains: list[SheetRow] | None = None,
    ) -> ReportDeliveryPlan:
        items: list[ReportDeliveryItem] = []
        problems: list[ReportDeliveryProblem] = []
        participants_by_id = {str(row.get("participant_id")): row for row in participants}
        self._append_captain_reports(
            items, problems, report, participants_by_id,
            team_captains or _legacy_team_captains(teams),
        )
        self._append_tracker_reports(items, problems, trackers)
        self._append_global_reports(items, problems, participants)
        return ReportDeliveryPlan(items=items, problems=problems)

    def _append_captain_reports(
        self, items: list[ReportDeliveryItem], problems: list[ReportDeliveryProblem],
        report: AllTeamsReportData, participants_by_id: dict[str, SheetRow],
        team_captains: list[SheetRow],
    ) -> None:
        for team in report.teams:
            assignments = [
                row for row in team_captains
                if str(row.get("team_id") or "") == team.team_id
                and row.get("is_active") is True
                and (
                    not self.flow_id
                    or str(row.get("flow_id") or "") == self.flow_id
                    or (
                        not row.get("flow_id")
                        and row.get("_assignment_source") == "legacy_teams"
                    )
                )
            ]
            for assignment in assignments:
                captain_id = str(assignment.get("captain_id") or "")
                captain = participants_by_id.get(captain_id)
                if not _eligible_captain(captain, team_id=team.team_id, flow_id=self.flow_id):
                    problems.append(ReportDeliveryProblem(
                        "ineligible_captain", "captain", captain_id,
                        self._scope(f"team:{team.team_id}"),
                    ))
                    continue
                self._append_team_items(
                    items=items, problems=problems, team=team,
                    recipient_type="captain", recipient_id=captain_id,
                    chat_id=captain_notification_chat_id(
                        assignment, participant=captain
                    ),
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


def _eligible_captain(
    row: SheetRow | None, *, team_id: str, flow_id: str | None
) -> bool:
    if row is None:
        return False
    return (
        row.get("role") == "captain"
        and str(row.get("status") or "").strip().lower() == "active"
        and row.get("consent_given") is True
        and str(row.get("team_id") or "") == team_id
        and (not flow_id or str(row.get("flow_id") or "") == flow_id)
    )


def _is_active(row: SheetRow) -> bool:
    value = row.get("is_active")
    return value is not False and value != "false"


@dataclass(frozen=True)
class ReportDeliveryService:
    repository: ReportStateRepository
    notification_router: NotificationRouter
    rate_limit_retry_budget: int = 2
    default_rate_limit_delay: float = 5.0
    sleep: Callable[[float], None] = default_sleep

    def deliver_plan(
        self,
        *,
        week_number: int,
        plan: ReportDeliveryPlan,
        sent_at: str,
    ) -> ReportRunResult:
        issues = list(plan.problems)
        rate_limit_retry_budget = [self.rate_limit_retry_budget]
        sent_count = skipped_count = 0
        for item in plan.items:
            outcome, issue = self._deliver_item(
                week_number=week_number,
                item=item,
                sent_at=sent_at,
                rate_limit_retry_budget=rate_limit_retry_budget,
            )
            sent_count += outcome == "sent"
            skipped_count += outcome == "skipped"
            if issue is not None:
                issues.append(issue)
        if issues:
            self._notify_admin(
                "report_delivery_summary",
                _delivery_issue_summary(week_number, issues),
            )
        return ReportRunResult(
            generated_count=len(plan.items), sent_count=sent_count,
            skipped_count=skipped_count, failed_count=len(issues),
        )

    def _deliver_item(
        self,
        *,
        week_number: int,
        item: ReportDeliveryItem,
        sent_at: str,
        rate_limit_retry_budget: list[int],
    ) -> tuple[str, ReportDeliveryProblem | None]:
        identity = dict(
            week_number=week_number, report_type=item.report_type.value, scope_id=item.scope_id,
            recipient_type=item.recipient.recipient_type, recipient_id=item.recipient.recipient_id,
        )
        if not self.repository.claim_delivery(
            **identity,
            chat_id=item.recipient.chat_id,
            sent_at=sent_at,
            file_path=str(item.file_path) if item.file_path else None,
        ):
            return "skipped", None

        try:
            self._send_item_with_retry(item, rate_limit_retry_budget)
        except Exception as exc:  # noqa: BLE001 - boundary isolates Telegram failures.
            reason = _delivery_failure_reason(exc)
            self.repository.record_delivery_attempt(
                **identity, chat_id=item.recipient.chat_id, status="failed", sent_at=sent_at,
                file_path=str(item.file_path) if item.file_path else None,
                error_message=reason,
            )
            return "failed", ReportDeliveryProblem(
                reason=reason,
                recipient_type=item.recipient.recipient_type,
                recipient_id=item.recipient.recipient_id,
                scope_id=item.scope_id,
                report_type=item.report_type.value,
            )
        self.repository.record_delivery_attempt(
            **identity, chat_id=item.recipient.chat_id, status="sent", sent_at=sent_at,
            file_path=str(item.file_path) if item.file_path else None,
        )
        return "sent", None

    def _send_item_with_retry(
        self, item: ReportDeliveryItem, rate_limit_retry_budget: list[int]
    ) -> None:
        while True:
            try:
                self._send_item(item)
                return
            except Exception as exc:  # noqa: BLE001 - classify external boundary failures.
                if _delivery_failure_reason(exc) != "telegram_rate_limited":
                    raise
                if rate_limit_retry_budget[0] <= 0:
                    raise
                rate_limit_retry_budget[0] -= 1
                retry_after = exc.retry_after if isinstance(exc, TelegramApiError) else None
                self.sleep(float(retry_after or self.default_rate_limit_delay))

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
    return compact[:1000]


def _delivery_failure_reason(error: Exception) -> str:
    if isinstance(error, TelegramApiError):
        message = str(error).lower()
        if error.status_code == 429 or "429" in message or "too many requests" in message:
            return "telegram_rate_limited"
        if "chat not found" in message or "bot was blocked by the user" in message:
            return "telegram_chat_unavailable"
        if error.status_code == 400 or "400" in message or "bad request" in message:
            return "telegram_bad_request"
        return "telegram_api_error"
    return "delivery_error"


def _delivery_issue_summary(
    week_number: int, issues: list[ReportDeliveryProblem]
) -> str:
    counts = Counter(issue.reason for issue in issues)
    grouped_ids: dict[str, list[str]] = {}
    for issue in issues:
        recipient = f"{issue.recipient_type}:{issue.recipient_id}"
        if issue.report_type:
            recipient = f"{recipient}/{issue.report_type}"
        recipients = grouped_ids.setdefault(issue.reason, [])
        if recipient not in recipients and len(recipients) < 8:
            recipients.append(recipient)
    details = "; ".join(
        f"{reason}={count} [{','.join(grouped_ids[reason])}]"
        for reason, count in sorted(counts.items())
    )
    hints = {
        "missing_chat_id": "заполнить Telegram ID",
        "ineligible_captain": "проверить роль, статус, согласие и команду капитана",
        "telegram_chat_unavailable": "получатель должен запустить Notification-бот и не блокировать его",
        "telegram_bad_request": "проверить адресата, размер и формат сообщения или PDF",
        "telegram_rate_limited": "Telegram ограничил частоту; попытки исчерпаны",
        "telegram_api_error": "проверить доступность Telegram",
        "delivery_error": "проверить техническую ошибку доставки",
        "missing_pdf": "проверить создание PDF",
        "missing_text": "проверить шаблон сообщения",
    }
    actions = "; ".join(
        f"{reason}: {hints.get(reason, 'проверить конфигурацию получателя')}"
        for reason in sorted(counts)
    )
    return (
        f"week={week_number} issues={len(issues)}; {details}. "
        f"Действия: {actions}. Повтор всего отчётного запуска отключён."
    )


def _legacy_team_captains(teams: list[SheetRow]) -> list[SheetRow]:
    return [
        {
            "flow_id": team.get("flow_id", ""),
            "team_id": team.get("team_id", ""),
            "captain_id": team.get("captain_id", ""),
            "is_primary": True,
            "is_active": team.get("is_active", True) is not False,
            "_assignment_source": "legacy_teams",
        }
        for team in teams
        if team.get("captain_id")
    ]
