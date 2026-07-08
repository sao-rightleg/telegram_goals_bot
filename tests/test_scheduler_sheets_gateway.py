from app.sheets.gateway import FakeSheetsGateway


def test_list_participants_returns_copies() -> None:
    gateway = FakeSheetsGateway(
        participants=[
            {"participant_id": "P001", "full_name": "Participant One"},
            {"participant_id": "P002", "full_name": "Participant Two"},
        ]
    )

    rows = gateway.list_participants()

    assert rows == [
        {"participant_id": "P001", "full_name": "Participant One"},
        {"participant_id": "P002", "full_name": "Participant Two"},
    ]
    rows[0]["full_name"] = "Mutated"
    assert gateway.list_participants()[0]["full_name"] == "Participant One"


def test_list_teams_returns_copies() -> None:
    gateway = FakeSheetsGateway(
        teams=[
            {"team_id": "T001", "team_name": "Team One", "captain_id": "C001"},
            {"team_id": "T002", "team_name": "Team Two", "captain_id": "C002"},
        ]
    )

    rows = gateway.list_teams()

    assert rows == [
        {"team_id": "T001", "team_name": "Team One", "captain_id": "C001"},
        {"team_id": "T002", "team_name": "Team Two", "captain_id": "C002"},
    ]
    rows[0]["team_name"] = "Mutated"
    assert gateway.list_teams()[0]["team_name"] == "Team One"


def test_get_tracker_returns_copy_or_none() -> None:
    gateway = FakeSheetsGateway(
        trackers=[
            {"tracker_id": "TR001", "telegram_id": 3001, "full_name": "Tracker One"},
            {"tracker_id": "TR002", "telegram_id": 3002, "full_name": "Tracker Two"},
        ]
    )

    row = gateway.get_tracker("TR002")

    assert row == {"tracker_id": "TR002", "telegram_id": 3002, "full_name": "Tracker Two"}
    assert gateway.get_tracker("TR404") is None
    assert row is not None
    row["full_name"] = "Mutated"
    assert gateway.get_tracker("TR002")["full_name"] == "Tracker Two"


def test_scheduler_gateway_extensions_do_not_break_existing_report_reads() -> None:
    gateway = FakeSheetsGateway(
        participants=[{"participant_id": "P001", "team_id": "T001"}],
        teams=[{"team_id": "T001", "tracker_id": "TR001"}],
        trackers=[{"tracker_id": "TR001", "telegram_id": 3001}],
        weekly_reports=[{"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}],
    )

    assert gateway.list_participants() == [{"participant_id": "P001", "team_id": "T001"}]
    assert gateway.list_teams() == [{"team_id": "T001", "tracker_id": "TR001"}]
    assert gateway.get_tracker("TR001") == {"tracker_id": "TR001", "telegram_id": 3001}
    assert gateway.find_weekly_report("P001", week_number=4) == {
        "weekly_report_id": "WR001",
        "participant_id": "P001",
        "week_number": 4,
    }
