import pytest

from app.sheets.gateway import (
    FakeSheetsGateway,
    GoogleSheetsGateway,
    GoogleSheetsSchemaError,
    validate_required_schema,
)
from tests.test_sheets_live_helpers import FakeSheetsService, minimal_live_sheets


def test_find_participant_by_telegram_id_returns_copy() -> None:
    gateway = FakeSheetsGateway(
        participants=[
            {
                "participant_id": "P001",
                "telegram_id": 1001,
                "full_name": "Participant One",
            }
        ]
    )

    row = gateway.find_participant_by_telegram_id(1001)
    assert row == {
        "participant_id": "P001",
        "telegram_id": 1001,
        "full_name": "Participant One",
    }

    assert row is not None
    row["full_name"] = "Mutated"

    assert gateway.find_participant_by_telegram_id(1001)["full_name"] == "Participant One"


def test_find_participant_by_unknown_telegram_id_returns_none() -> None:
    gateway = FakeSheetsGateway(participants=[{"participant_id": "P001", "telegram_id": 1001}])

    assert gateway.find_participant_by_telegram_id(404) is None


def test_get_participant_returns_copy_by_id() -> None:
    gateway = FakeSheetsGateway(
        participants=[
            {"participant_id": "P001", "telegram_id": 1001, "full_name": "Participant One"},
            {"participant_id": "P002", "telegram_id": 1002, "full_name": "Participant Two"},
        ]
    )

    row = gateway.get_participant("P002")

    assert row == {"participant_id": "P002", "telegram_id": 1002, "full_name": "Participant Two"}
    assert gateway.get_participant("P404") is None
    assert row is not None
    row["full_name"] = "Mutated"
    assert gateway.get_participant("P002")["full_name"] == "Participant Two"


def test_list_participants_by_team_returns_copies() -> None:
    gateway = FakeSheetsGateway(
        participants=[
            {"participant_id": "P001", "team_id": "T001", "full_name": "Participant One"},
            {"participant_id": "P002", "team_id": "T002", "full_name": "Participant Two"},
            {"participant_id": "P003", "team_id": "T001", "full_name": "Participant Three"},
        ]
    )

    rows = gateway.list_participants_by_team("T001")

    assert rows == [
        {"participant_id": "P001", "team_id": "T001", "full_name": "Participant One"},
        {"participant_id": "P003", "team_id": "T001", "full_name": "Participant Three"},
    ]
    rows[0]["full_name"] = "Mutated"
    assert gateway.list_participants_by_team("T001")[0]["full_name"] == "Participant One"


def test_update_participant_consent_updates_only_matching_participant() -> None:
    gateway = FakeSheetsGateway(
        participants=[
            {"participant_id": "P001", "telegram_id": 1001, "consent_given": False},
            {"participant_id": "P002", "telegram_id": 1002, "consent_given": False},
        ]
    )

    gateway.update_participant_consent(
        "P001",
        consent_given=True,
        consent_given_at="2026-07-02T10:00:00+05:00",
    )

    assert gateway.find_participant_by_telegram_id(1001)["consent_given"] is True
    assert (
        gateway.find_participant_by_telegram_id(1001)["consent_given_at"]
        == "2026-07-02T10:00:00+05:00"
    )
    assert gateway.find_participant_by_telegram_id(1002)["consent_given"] is False


def test_update_participant_consent_missing_participant_fails_clearly() -> None:
    gateway = FakeSheetsGateway(participants=[])

    with pytest.raises(KeyError, match="P404"):
        gateway.update_participant_consent(
            "P404",
            consent_given=True,
            consent_given_at="2026-07-02T10:00:00+05:00",
        )


def test_get_active_goal_filters_by_participant_and_status() -> None:
    gateway = FakeSheetsGateway(
        goals=[
            {"goal_id": "G001", "participant_id": "P001", "goal_status": "paused"},
            {"goal_id": "G002", "participant_id": "P002", "goal_status": "active"},
            {"goal_id": "G003", "participant_id": "P001", "goal_status": "active"},
        ]
    )

    assert gateway.get_active_goal("P001") == {
        "goal_id": "G003",
        "participant_id": "P001",
        "goal_status": "active",
    }


def test_list_planned_steps_filters_by_participant_and_goal() -> None:
    gateway = FakeSheetsGateway(
        planned_steps=[
            {"step_id": "S001", "participant_id": "P001", "goal_id": "G001"},
            {"step_id": "S002", "participant_id": "P001", "goal_id": "G002"},
            {"step_id": "S003", "participant_id": "P002", "goal_id": "G001"},
        ]
    )

    assert gateway.list_planned_steps("P001", "G001") == [
        {"step_id": "S001", "participant_id": "P001", "goal_id": "G001"}
    ]


def test_list_weekly_status_history_filters_by_participant() -> None:
    gateway = FakeSheetsGateway(
        weekly_reports=[
            {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 1},
            {"weekly_report_id": "WR002", "participant_id": "P002", "week_number": 1},
            {"weekly_report_id": "WR003", "participant_id": "P001", "week_number": 2},
        ]
    )

    assert gateway.list_weekly_status_history("P001") == [
        {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 1},
        {"weekly_report_id": "WR003", "participant_id": "P001", "week_number": 2},
    ]


def test_live_gateway_finds_participant_by_telegram_id() -> None:
    service = FakeSheetsService(minimal_live_sheets())
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")

    row = gateway.find_participant_by_telegram_id(1001)

    assert row is not None
    assert row["participant_id"] == "P001"
    assert row["telegram_id"] == 1001
    assert row["consent_given"] is False


def test_live_gateway_updates_participant_consent() -> None:
    service = FakeSheetsService(minimal_live_sheets())
    gateway = GoogleSheetsGateway(service=service, spreadsheet_id="sheet-id")

    gateway.update_participant_consent(
        "P001",
        consent_given=True,
        consent_given_at="2026-07-02T10:00:00+05:00",
    )

    row = gateway.find_participant_by_telegram_id(1001)
    assert row is not None
    assert row["consent_given"] is True
    assert row["consent_given_at"] == "2026-07-02T10:00:00+05:00"


def test_live_schema_validation_allows_extra_columns() -> None:
    sheets = minimal_live_sheets(
        Participants=[
            [
                "participant_id",
                "telegram_id",
                "username",
                "full_name",
                "team_id",
                "role",
                "status",
                "consent_given",
                "consent_given_at",
                "manual_extra_column",
            ]
        ]
    )

    validate_required_schema(FakeSheetsService(sheets), spreadsheet_id="sheet-id")


def test_live_schema_validation_fails_for_missing_required_column() -> None:
    sheets = minimal_live_sheets(Participants=[["participant_id", "telegram_id"]])

    with pytest.raises(GoogleSheetsSchemaError) as error:
        validate_required_schema(FakeSheetsService(sheets), spreadsheet_id="sheet-id")

    assert "Participants" in str(error.value)
    assert "role" in str(error.value)
