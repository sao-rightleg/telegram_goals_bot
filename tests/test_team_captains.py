from app.services.team_captains import (
    captain_notification_chat_id,
    list_team_captain_assignments,
)
from app.sheets.gateway import FakeSheetsGateway


def test_explicit_assignments_and_unmigrated_legacy_teams_are_combined() -> None:
    gateway = FakeSheetsGateway(
        teams=[
            {
                "flow_id": "FLOW_1", "team_id": "T001",
                "captain_id": "OLD_1", "captain_telegram_id": 101,
                "is_active": True,
            },
            {
                "flow_id": "FLOW_1", "team_id": "T002",
                "captain_id": "OLD_2", "captain_telegram_id": 102,
                "is_active": True,
            },
        ],
        team_captains=[
            {
                "flow_id": "FLOW_1", "team_id": "T001",
                "captain_id": "NEW_1", "captain_telegram_id": 201,
                "is_primary": True, "is_active": True,
            },
            {
                "flow_id": "FLOW_1", "team_id": "T001",
                "captain_id": "NEW_2", "captain_telegram_id": 202,
                "is_primary": False, "is_active": True,
            },
        ],
    )

    assignments = list_team_captain_assignments(gateway)

    assert [row["captain_id"] for row in assignments] == ["NEW_1", "NEW_2", "OLD_2"]


def test_inactive_explicit_assignment_prevents_legacy_reactivation() -> None:
    gateway = FakeSheetsGateway(
        teams=[{
            "flow_id": "FLOW_1", "team_id": "T001",
            "captain_id": "OLD_1", "captain_telegram_id": 101,
            "is_active": True,
        }],
        team_captains=[{
            "flow_id": "FLOW_1", "team_id": "T001",
            "captain_id": "NEW_1", "captain_telegram_id": 201,
            "is_primary": True, "is_active": False,
        }],
    )

    assignments = list_team_captain_assignments(gateway)

    assert [row["captain_id"] for row in assignments] == ["NEW_1"]


def test_bound_flow_prevents_blank_legacy_row_from_duplicating_explicit_team() -> None:
    gateway = FakeSheetsGateway(
        teams=[{
            "flow_id": "", "team_id": "T001", "captain_id": "OLD_1",
            "captain_telegram_id": 101, "is_active": True,
        }],
        team_captains=[{
            "flow_id": "FLOW_1", "team_id": "T001", "captain_id": "NEW_1",
            "captain_telegram_id": 201, "is_primary": True, "is_active": True,
        }],
    )

    assignments = list_team_captain_assignments(
        gateway, default_flow_id="FLOW_1"
    )

    assert [row["captain_id"] for row in assignments] == ["NEW_1"]


def test_notification_chat_requires_verified_matching_start() -> None:
    participant = {"telegram_id": 201}

    assert captain_notification_chat_id(
        {
            "captain_telegram_id": 201,
            "notification_bot_chat_id": "201",
            "notification_bot_status": "active",
        },
        participant=participant,
    ) == "201"
    assert captain_notification_chat_id(
        {
            "captain_telegram_id": 201,
            "notification_bot_chat_id": "999",
            "notification_bot_status": "active",
        },
        participant=participant,
    ) is None
    assert captain_notification_chat_id(
        {
            "captain_telegram_id": 201,
            "notification_bot_chat_id": "201",
            "notification_bot_status": "blocked",
        },
        participant=participant,
    ) is None
    assert captain_notification_chat_id(
        {"_assignment_source": "legacy_teams"},
        participant=participant,
    ) is None
