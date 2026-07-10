import pytest

from app.sheets.gateway import FakeSheetsGateway, GoogleSheetsGateway
from tests.test_sheets_live_helpers import FakeSheetsService, minimal_live_sheets


def test_find_weekly_report_filters_by_participant_and_week() -> None:
    gateway = FakeSheetsGateway(
        weekly_reports=[
            {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 1},
            {"weekly_report_id": "WR002", "participant_id": "P002", "week_number": 2},
            {"weekly_report_id": "WR003", "participant_id": "P001", "week_number": 3},
        ]
    )

    row = gateway.find_weekly_report("P001", week_number=3)

    assert row == {"weekly_report_id": "WR003", "participant_id": "P001", "week_number": 3}
    assert gateway.find_weekly_report("P001", week_number=2) is None

    assert row is not None
    row["weekly_report_id"] = "MUTATED"
    assert gateway.find_weekly_report("P001", week_number=3)["weekly_report_id"] == "WR003"


def test_append_weekly_report_step_stores_relation_copy() -> None:
    gateway = FakeSheetsGateway()
    relation = {
        "weekly_report_step_id": "WRS001",
        "weekly_report_id": "WR001",
        "participant_id": "P001",
        "goal_id": "G001",
        "step_id": "S001",
        "week_number": 2,
        "relation_status": "closed",
    }

    gateway.append_weekly_report_step(relation)
    relation["relation_status"] = "mutated"

    stored = gateway.list_weekly_report_steps()
    assert stored == [
        {
            "weekly_report_step_id": "WRS001",
            "weekly_report_id": "WR001",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_id": "S001",
            "week_number": 2,
            "relation_status": "closed",
        }
    ]

    stored[0]["relation_status"] = "mutated again"
    assert gateway.list_weekly_report_steps()[0]["relation_status"] == "closed"


def test_close_planned_steps_updates_only_selected_owned_steps() -> None:
    gateway = FakeSheetsGateway(
        planned_steps=[
            _step("S001", "P001", "G001", "open"),
            _step("S002", "P001", "G001", "open"),
            _step("S003", "P001", "G001", "open"),
            _step("S004", "P001", "G002", "open"),
            _step("S005", "P002", "G001", "open"),
        ]
    )

    gateway.close_planned_steps(
        "P001",
        "G001",
        ["S001", "S003"],
        closed_week_number=2,
        closed_report_id="WR001",
        closed_at="2026-07-12T23:00:00+05:00",
    )

    steps = {row["step_id"]: row for row in gateway.list_planned_steps("P001", "G001")}
    assert steps["S001"]["step_status"] == "closed"
    assert steps["S001"]["closed_week_number"] == 2
    assert steps["S001"]["closed_report_id"] == "WR001"
    assert steps["S001"]["closed_at"] == "2026-07-12T23:00:00+05:00"
    assert steps["S002"]["step_status"] == "open"
    assert steps["S003"]["step_status"] == "closed"

    assert gateway.list_planned_steps("P001", "G002")[0]["step_status"] == "open"
    assert gateway.list_planned_steps("P002", "G001")[0]["step_status"] == "open"


def test_close_planned_steps_rejects_missing_or_foreign_steps_without_partial_update() -> None:
    gateway = FakeSheetsGateway(
        planned_steps=[
            _step("S001", "P001", "G001", "open"),
            _step("S002", "P002", "G001", "open"),
        ]
    )

    with pytest.raises(KeyError, match="S404"):
        gateway.close_planned_steps(
            "P001",
            "G001",
            ["S001", "S404"],
            closed_week_number=2,
            closed_report_id="WR001",
            closed_at="2026-07-12T23:00:00+05:00",
        )

    with pytest.raises(KeyError, match="S002"):
        gateway.close_planned_steps(
            "P001",
            "G001",
            ["S002"],
            closed_week_number=2,
            closed_report_id="WR001",
            closed_at="2026-07-12T23:00:00+05:00",
        )

    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "open"
    assert gateway.list_planned_steps("P002", "G001")[0]["step_status"] == "open"


def test_existing_gateway_behavior_is_preserved() -> None:
    gateway = FakeSheetsGateway()

    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001"})
    gateway.append_insight({"insight_id": "I001", "participant_id": "P001"})

    assert gateway.list_weekly_reports() == [
        {"weekly_report_id": "WR001", "participant_id": "P001"}
    ]
    assert gateway.list_insights() == [{"insight_id": "I001", "participant_id": "P001"}]


def test_live_gateway_appends_weekly_report_and_steps() -> None:
    service = FakeSheetsService(minimal_live_sheets())
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")

    gateway.append_weekly_report(
        {
            "weekly_report_id": "WR001",
            "participant_id": "P001",
            "team_id": "T001",
            "goal_id": "G001",
            "week_number": 4,
            "status_symbol": "🟩",
            "status_code": "green",
            "score": 1,
            "report_text": "Done",
            "flow_source": "participant_bot",
        }
    )
    gateway.append_weekly_report_step(
        {
            "weekly_report_step_id": "WRS001",
            "weekly_report_id": "WR001",
            "participant_id": "P001",
            "step_id": "S001",
            "relation_status": "closed",
            "created_at": "2026-07-02T10:00:00+05:00",
        }
    )

    report = gateway.find_weekly_report("P001", week_number=4)
    assert report is not None
    assert report["weekly_report_id"] == "WR001"
    assert report["score"] == 1
    assert report["flow_source"] == "participant_bot"
    relation = gateway.list_weekly_report_steps()[0]
    assert relation["weekly_report_step_id"] == "WRS001"
    assert relation["relation_status"] == "closed"


def test_live_gateway_closes_planned_steps() -> None:
    service = FakeSheetsService(minimal_live_sheets())
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")

    gateway.close_planned_steps(
        "P001",
        "G001",
        ["S001"],
        closed_week_number=4,
        closed_report_id="WR001",
        closed_at="2026-07-02T10:00:00+05:00",
    )

    step = gateway.list_planned_steps("P001", "G001")[0]
    assert step["step_status"] == "closed"
    assert step["closed_week_number"] == 4
    assert step["closed_report_id"] == "WR001"


def _step(step_id: str, participant_id: str, goal_id: str, status: str) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_status": status,
    }
