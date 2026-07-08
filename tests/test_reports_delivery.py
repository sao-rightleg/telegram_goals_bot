from pathlib import Path

from app.reports.delivery import ReportDeliveryPlanner
from app.reports.models import (
    AllTeamsReportData,
    ReportType,
    TeamReportData,
)


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
