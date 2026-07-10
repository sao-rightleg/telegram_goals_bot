from app.sheets.gateway import FakeSheetsGateway, GoogleSheetsGateway
from tests.test_sheets_live_helpers import FakeSheetsService, minimal_live_sheets


def test_fake_gateway_lists_report_goal_rows_as_copies() -> None:
    gateway = FakeSheetsGateway(
        goals=[
            {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
            {"goal_id": "G002", "participant_id": "P002", "goal_status": "achieved"},
        ]
    )

    rows = gateway.list_goals()

    assert rows == [
        {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
        {"goal_id": "G002", "participant_id": "P002", "goal_status": "achieved"},
    ]
    rows[0]["goal_status"] = "mutated"
    assert gateway.list_goals()[0]["goal_status"] == "active"


def test_fake_gateway_lists_planned_steps_for_all_participants() -> None:
    gateway = FakeSheetsGateway(
        planned_steps=[
            {"step_id": "S001", "participant_id": "P001", "goal_id": "G001"},
            {"step_id": "S002", "participant_id": "P002", "goal_id": "G002"},
        ]
    )

    rows = gateway.list_planned_steps_all()

    assert [row["step_id"] for row in rows] == ["S001", "S002"]
    rows[0]["step_id"] = "MUTATED"
    assert gateway.list_planned_steps_all()[0]["step_id"] == "S001"


def test_fake_gateway_filters_weekly_reports_by_week() -> None:
    gateway = FakeSheetsGateway(
        weekly_reports=[
            {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4},
            {"weekly_report_id": "WR002", "participant_id": "P002", "week_number": 5},
            {"weekly_report_id": "WR003", "participant_id": "P003", "week_number": 5},
        ]
    )

    rows = gateway.list_weekly_reports_for_week(5)

    assert [row["weekly_report_id"] for row in rows] == ["WR002", "WR003"]
    rows[0]["weekly_report_id"] = "MUTATED"
    assert gateway.list_weekly_reports_for_week(5)[0]["weekly_report_id"] == "WR002"
    assert gateway.list_weekly_reports_for_week(404) == []


def test_fake_gateway_lists_weekly_report_step_relations() -> None:
    gateway = FakeSheetsGateway(
        weekly_report_steps=[
            {"weekly_report_step_id": "WRS001", "weekly_report_id": "WR001", "step_id": "S001"},
            {"weekly_report_step_id": "WRS002", "weekly_report_id": "WR002", "step_id": "S002"},
        ]
    )

    rows = gateway.list_weekly_report_steps_all()

    assert [row["weekly_report_step_id"] for row in rows] == ["WRS001", "WRS002"]
    rows[0]["weekly_report_step_id"] = "MUTATED"
    assert gateway.list_weekly_report_steps_all()[0]["weekly_report_step_id"] == "WRS001"


def test_fake_gateway_filters_insights_by_week() -> None:
    gateway = FakeSheetsGateway(
        insights=[
            {"insight_id": "I001", "participant_id": "P001", "week_number": 4},
            {"insight_id": "I002", "participant_id": "P002", "week_number": 5},
            {"insight_id": "I003", "participant_id": "P003", "week_number": 5},
        ]
    )

    rows = gateway.list_insights_for_week(5)

    assert [row["insight_id"] for row in rows] == ["I002", "I003"]
    rows[0]["insight_id"] = "MUTATED"
    assert gateway.list_insights_for_week(5)[0]["insight_id"] == "I002"
    assert gateway.list_insights_for_week(404) == []


def test_live_gateway_lists_report_facts() -> None:
    sheets = minimal_live_sheets(
        WeeklyReports=[
            [
                "weekly_report_id",
                "participant_id",
                "team_id",
                "goal_id",
                "week_number",
                "status_score",
                "submitted_source",
            ],
            ["WR001", "P001", "T001", "G001", "4", "1", "participant_bot"],
            ["WR002", "P002", "T002", "G002", "5", "0.5", "captain_manual"],
        ],
        Insights=[
            ["insight_id", "participant_id", "goal_id", "week_number", "insight_text"],
            ["I001", "P001", "G001", "4", "text"],
        ],
    )
    gateway = GoogleSheetsGateway(service=FakeSheetsService(sheets), spreadsheet_id="sheet-id")

    reports = gateway.list_weekly_reports_for_week(4)
    assert len(reports) == 1
    assert reports[0]["weekly_report_id"] == "WR001"
    assert reports[0]["score"] == 1
    assert reports[0]["flow_source"] == "participant_bot"
    assert [row["goal_id"] for row in gateway.list_goals()] == ["G001"]
    assert [row["step_id"] for row in gateway.list_planned_steps_all()] == ["S001"]
    assert [row["insight_id"] for row in gateway.list_insights_for_week(4)] == ["I001"]
