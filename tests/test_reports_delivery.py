from pathlib import Path

from app.bot.clients import BotPurpose, FakeBotClient, OutgoingMessage
from app.reports.delivery import ReportDeliveryPlanner
from app.reports.models import (
    AllTeamsReportData,
    ReportDeliveryItem,
    ReportRecipient,
    ReportType,
    TeamReportData,
)
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.storage.reports import ReportStateRepository
from app.storage.sqlite import initialize_schema


def test_captain_plan_contains_only_own_team_summary_and_pdf() -> None:
    plan = _planner().build_plan(_report_data(), participants=_participants(), teams=_teams(), trackers=_trackers())

    captain_items = [
        item
        for item in plan.items
        if item.recipient.recipient_type == "captain" and item.recipient.recipient_id == "C001"
    ]

    assert [(item.report_type, item.scope_id) for item in captain_items] == [
        (ReportType.TELEGRAM_TEAM_SUMMARY, "T001"),
        (ReportType.PDF_TEAM_REPORT, "T001"),
    ]
    assert all(item.recipient.recipient_id == "C001" for item in captain_items)
    assert all(item.recipient.chat_id == "2001" for item in captain_items)


def test_tracker_plan_contains_only_assigned_team_reports() -> None:
    plan = _planner().build_plan(_report_data(), participants=_participants(), teams=_teams(), trackers=_trackers())

    tracker_items = [item for item in plan.items if item.recipient.recipient_type == "tracker"]

    assert {(item.recipient.recipient_id, item.report_type, item.scope_id) for item in tracker_items} == {
        ("TR_MALE", ReportType.TELEGRAM_TEAM_SUMMARY, "T001"),
        ("TR_MALE", ReportType.PDF_TEAM_REPORT, "T001"),
        ("TR_FEMALE", ReportType.TELEGRAM_TEAM_SUMMARY, "T002"),
        ("TR_FEMALE", ReportType.PDF_TEAM_REPORT, "T002"),
    }


def test_admin_plan_contains_all_reports_full_summary_and_comparison() -> None:
    plan = _planner().build_plan(_report_data(), participants=_participants(), teams=_teams(), trackers=_trackers())

    admin_items = [item for item in plan.items if item.recipient.recipient_type == "admin"]

    assert {(item.report_type, item.scope_id) for item in admin_items} == {
        (ReportType.TELEGRAM_TEAM_SUMMARY, "T001"),
        (ReportType.PDF_TEAM_REPORT, "T001"),
        (ReportType.TELEGRAM_TEAM_SUMMARY, "T002"),
        (ReportType.PDF_TEAM_REPORT, "T002"),
        (ReportType.FULL_SUMMARY, "global"),
        (ReportType.GROUP_COMPARISON, "global"),
    }


def test_sitnikov_plan_contains_all_reports_full_summary_and_comparison() -> None:
    plan = _planner().build_plan(_report_data(), participants=_participants(), teams=_teams(), trackers=_trackers())

    sitnikov_items = [item for item in plan.items if item.recipient.recipient_type == "sitnikov"]

    assert {(item.report_type, item.scope_id) for item in sitnikov_items} == {
        (ReportType.TELEGRAM_TEAM_SUMMARY, "T001"),
        (ReportType.PDF_TEAM_REPORT, "T001"),
        (ReportType.TELEGRAM_TEAM_SUMMARY, "T002"),
        (ReportType.PDF_TEAM_REPORT, "T002"),
        (ReportType.FULL_SUMMARY, "global"),
        (ReportType.GROUP_COMPARISON, "global"),
    }


def test_captains_and_trackers_never_receive_group_comparison() -> None:
    plan = _planner().build_plan(_report_data(), participants=_participants(), teams=_teams(), trackers=_trackers())

    restricted_items = [
        item
        for item in plan.items
        if item.recipient.recipient_type in {"captain", "tracker"}
    ]

    assert all(item.report_type is not ReportType.GROUP_COMPARISON for item in restricted_items)


def test_missing_chat_id_is_planned_as_problem_not_delivery_item() -> None:
    participants = [
        row
        for row in _participants()
        if row["participant_id"] != "C001"
    ] + [
        {
            "participant_id": "C001",
            "role": "captain",
            "team_id": "T001",
            "full_name": "Капитан без чата",
        }
    ]

    plan = _planner().build_plan(_report_data(), participants=participants, teams=_teams(), trackers=_trackers())

    captain_items = [
        item
        for item in plan.items
        if item.recipient.recipient_type == "captain" and item.scope_id == "T001"
    ]
    assert captain_items == []
    assert any(problem.recipient_id == "C001" and problem.scope_id == "T001" for problem in plan.problems)


def test_delivery_sends_text_and_documents_through_notification_bot(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryService

    service, _repository, _main_bot, _error_bot, notification_bot = _delivery_service(tmp_path)
    captains_only = [row for row in _participants() if row["role"] == "captain"]
    plan = _planner().build_plan(_report_data(), participants=captains_only, teams=_teams(), trackers=[])

    result = service.deliver_plan(week_number=5, plan=plan, sent_at="2026-07-12T23:59:00+05:00")

    assert result.sent_count == 4
    assert [message.chat_id for message in notification_bot.sent_messages] == ["2001", "2002"]
    assert [document.chat_id for document in notification_bot.sent_documents] == ["2001", "2002"]


def test_delivery_skips_already_successful_items(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryService

    service, repository, _main_bot, _error_bot, notification_bot = _delivery_service(tmp_path)
    plan = _single_item_plan()
    repository.record_delivery_attempt(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
        chat_id="2001",
        status="sent",
        sent_at="2026-07-12T23:58:00+05:00",
    )

    result = service.deliver_plan(week_number=5, plan=plan, sent_at="2026-07-12T23:59:00+05:00")

    assert result.skipped_count == 1
    assert notification_bot.sent_messages == []


def test_delivery_records_sent_items_in_repository(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryService

    service, repository, _main_bot, _error_bot, _notification_bot = _delivery_service(tmp_path)

    service.deliver_plan(week_number=5, plan=_single_item_plan(), sent_at="2026-07-12T23:59:00+05:00")

    assert repository.has_successful_delivery(
        week_number=5,
        report_type="telegram_team_summary",
        scope_id="T001",
        recipient_type="captain",
        recipient_id="C001",
    )


def test_missing_chat_id_notifies_admin_and_continues(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryProblem, ReportDeliveryPlan, ReportDeliveryService

    service, _repository, _main_bot, error_bot, notification_bot = _delivery_service(tmp_path)
    plan = ReportDeliveryPlan(
        items=_single_item_plan().items,
        problems=[
            ReportDeliveryProblem(
                reason="missing_chat_id",
                recipient_type="captain",
                recipient_id="C404",
                scope_id="T404",
            )
        ],
    )

    result = service.deliver_plan(week_number=5, plan=plan, sent_at="2026-07-12T23:59:00+05:00")

    assert result.sent_count == 1
    assert result.failed_count == 1
    assert len(notification_bot.sent_messages) == 1
    assert "report_delivery_problem" in error_bot.sent_messages[0].text
    assert "C404" in error_bot.sent_messages[0].text


def test_send_failure_notifies_admin_records_failure_and_continues(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryService

    service, _repository, _main_bot, error_bot, notification_bot = _delivery_service(
        tmp_path,
        notification_bot=FailingOnceBot(BotPurpose.NOTIFICATION),
    )
    plan = _two_text_items_plan()

    result = service.deliver_plan(week_number=5, plan=plan, sent_at="2026-07-12T23:59:00+05:00")

    assert result.sent_count == 1
    assert result.failed_count == 1
    assert len(notification_bot.sent_messages) == 1
    assert "report_delivery_failed" in error_bot.sent_messages[0].text


def test_admin_error_is_sanitized(tmp_path: Path) -> None:
    from app.reports.delivery import ReportDeliveryService

    service, _repository, _main_bot, error_bot, _notification_bot = _delivery_service(
        tmp_path,
        notification_bot=AlwaysFailingBot(BotPurpose.NOTIFICATION),
    )

    service.deliver_plan(
        week_number=5,
        plan=_single_item_plan(text="личный отчёт участника token=secret"),
        sent_at="2026-07-12T23:59:00+05:00",
    )

    error_text = error_bot.sent_messages[0].text
    assert "token=secret" not in error_text
    assert "личный отчёт" not in error_text
    assert "telegram_team_summary" in error_text


def _planner() -> ReportDeliveryPlanner:
    return ReportDeliveryPlanner(
        team_summary_texts={
            "T001": "summary T001",
            "T002": "summary T002",
        },
        team_pdf_paths={
            "T001": Path("/tmp/T001.pdf"),
            "T002": Path("/tmp/T002.pdf"),
        },
        full_summary_text="full summary",
        group_comparison_text="comparison",
    )


def _delivery_service(
    tmp_path: Path,
    *,
    notification_bot: FakeBotClient | None = None,
) -> tuple[object, ReportStateRepository, FakeBotClient, FakeBotClient, FakeBotClient]:
    from app.reports.delivery import ReportDeliveryService

    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    selected_notification_bot = notification_bot or FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=selected_notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return (
        ReportDeliveryService(repository=repository, notification_router=router),
        repository,
        main_bot,
        error_bot,
        selected_notification_bot,
    )


def _single_item_plan(*, text: str = "summary") -> object:
    from app.reports.delivery import ReportDeliveryPlan

    return ReportDeliveryPlan(
        items=[
            ReportDeliveryItem(
                report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                scope_id="T001",
                recipient=ReportRecipient(
                    recipient_type="captain",
                    recipient_id="C001",
                    chat_id="2001",
                    team_scope_id="T001",
                ),
                text=text,
            )
        ]
    )


def _two_text_items_plan() -> object:
    from app.reports.delivery import ReportDeliveryPlan

    return ReportDeliveryPlan(
        items=[
            ReportDeliveryItem(
                report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                scope_id="T001",
                recipient=ReportRecipient("captain", "C001", "2001", "T001"),
                text="first",
            ),
            ReportDeliveryItem(
                report_type=ReportType.TELEGRAM_TEAM_SUMMARY,
                scope_id="T002",
                recipient=ReportRecipient("captain", "C002", "2002", "T002"),
                text="second",
            ),
        ]
    )


def _report_data() -> AllTeamsReportData:
    return AllTeamsReportData(
        week_number=5,
        total_active_count=3,
        total_dropped_count=0,
        average_victory_percent=75,
        teams=(
            _team("T001", "Мужская команда", "C001"),
            _team("T002", "Женская команда", "C002"),
        ),
    )


def _team(team_id: str, name: str, captain_id: str) -> TeamReportData:
    return TeamReportData(
        week_number=5,
        team_id=team_id,
        team_name=name,
        captain_id=captain_id,
        captain_name="Капитан",
        active_count=1,
        dropped_count=0,
        status_distribution={"green": 1, "blue": 0, "red": 0, "gray": 0},
        weekly_victory_percent=100,
        participants=(),
    )


def _participants() -> list[dict[str, object]]:
    return [
        {"participant_id": "C001", "role": "captain", "team_id": "T001", "telegram_id": 2001},
        {"participant_id": "C002", "role": "captain", "team_id": "T002", "telegram_id": 2002},
        {"participant_id": "A001", "role": "admin", "telegram_id": 9001},
        {"participant_id": "S001", "role": "sitnikov", "telegram_id": 9002},
    ]


def _teams() -> list[dict[str, object]]:
    return [
        {"team_id": "T001", "team_name": "Мужская команда", "gender": "male", "captain_id": "C001"},
        {"team_id": "T002", "team_name": "Женская команда", "gender": "female", "captain_id": "C002"},
    ]


def _trackers() -> list[dict[str, object]]:
    return [
        {"tracker_id": "TR_MALE", "telegram_id": 3001, "gender_scope": "male", "is_active": True},
        {"tracker_id": "TR_FEMALE", "telegram_id": 3002, "gender_scope": "female", "is_active": True},
    ]


class FailingOnceBot(FakeBotClient):
    def __init__(self, purpose: BotPurpose) -> None:
        super().__init__(purpose)
        self._failed = False

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        if not self._failed:
            self._failed = True
            raise RuntimeError("telegram token=secret unavailable")
        return super().send_message(chat_id=chat_id, text=text)


class AlwaysFailingBot(FakeBotClient):
    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        raise RuntimeError("telegram token=secret unavailable")
