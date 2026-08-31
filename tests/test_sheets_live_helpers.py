from __future__ import annotations

from collections.abc import Iterable


class FakeSheetsService:
    def __init__(
        self,
        sheets: dict[str, list[list[object]]],
        *,
        spreadsheets: dict[str, dict[str, list[list[object]]]] | None = None,
    ) -> None:
        self.sheets = {name: [list(row) for row in rows] for name, rows in sheets.items()}
        self.spreadsheet_docs = {
            spreadsheet_id: {name: [list(row) for row in rows] for name, rows in spreadsheet.items()}
            for spreadsheet_id, spreadsheet in (spreadsheets or {}).items()
        }
        self.appended: list[tuple[str, list[object]]] = []
        self.updated: list[tuple[str, list[list[object]]]] = []

    def spreadsheets(self) -> "FakeSheetsService":
        return self

    def values(self) -> "FakeSheetsService":
        return self

    def get_values(self, spreadsheet_id: str, range_name: str) -> list[list[object]]:
        sheets = self._sheets_for(spreadsheet_id)
        title = _sheet_title(range_name)
        return [list(row) for row in sheets.get(title, [])]

    def get(self, *, spreadsheetId: str, range: str | None = None):  # type: ignore[override]
        sheets = self._sheets_for(spreadsheetId)
        if range is None:
            return _Executable(
                {
                    "sheets": [
                        {"properties": {"title": title}}
                        for title in sheets
                    ]
                }
            )
        return _Executable({"values": self.get_values(spreadsheetId, range)})

    def append(
        self,
        *,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        insertDataOption: str,
        body: dict[str, object],
    ) -> "_Executable":
        values = _body_values(body)
        title = _sheet_title(range)
        self._sheets_for(spreadsheetId).setdefault(title, []).extend(values)
        for row in values:
            self.appended.append((title, row))
        return _Executable({"updates": {"updatedRows": len(values)}})

    def update(
        self,
        *,
        spreadsheetId: str,
        range: str,
        valueInputOption: str,
        body: dict[str, object],
    ) -> "_Executable":
        values = _body_values(body)
        title = _sheet_title(range)
        start_row = _start_row(range)
        rows = self._sheets_for(spreadsheetId).setdefault(title, [])
        for offset, row in enumerate(values):
            index = start_row + offset - 1
            while len(rows) <= index:
                rows.append([])
            rows[index] = list(row)
        self.updated.append((range, values))
        return _Executable({"updatedRows": len(values)})

    def _sheets_for(self, spreadsheet_id: str) -> dict[str, list[list[object]]]:
        return self.spreadsheet_docs.get(spreadsheet_id, self.sheets)


class _Executable:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def execute(self) -> dict[str, object]:
        return self._payload


def _sheet_title(range_name: str) -> str:
    return range_name.split("!", 1)[0].strip("'")


def _start_row(range_name: str) -> int:
    if "!" not in range_name:
        return 1
    coordinates = range_name.split("!", 1)[1]
    digits = ""
    for character in coordinates:
        if character.isdigit():
            digits += character
        elif digits:
            break
    return int(digits or "1")


def _body_values(body: dict[str, object]) -> list[list[object]]:
    values = body.get("values")
    if not isinstance(values, Iterable):
        return []
    return [list(row) for row in values if isinstance(row, Iterable) and not isinstance(row, str)]


def minimal_live_sheets(**overrides: list[list[object]]) -> dict[str, list[list[object]]]:
    sheets: dict[str, list[list[object]]] = {
        "Participants": [
            [
                "flow_id",
                "participant_id",
                "telegram_id",
                "username",
                "first_name",
                "last_name",
                "full_name",
                "team_id",
                "team_name",
                "captain_id",
                "tracker_id",
                "role",
                "status",
                "participant_stage",
                "consent_given",
                "consent_given_at",
                "consent_status",
                "bot_started_at",
                "onboarding_completed_at",
                "last_stage_updated_at",
                "created_at",
                "updated_at",
            ],
            [
                "test-live-2026",
                "P001",
                "1001",
                "p001",
                "Participant",
                "One",
                "Participant One",
                "T001",
                "Team One",
                "C001",
                "TR001",
                "participant",
                "active",
                "invited",
                "FALSE",
                "",
                "pending",
                "",
                "",
                "",
                "2026-05-20T10:00:00+05:00",
                "2026-05-20T10:00:00+05:00",
            ],
        ],
        "Teams": [["flow_id", "team_id", "team_name", "gender", "captain_id", "tracker_id", "is_active"]],
        "Trackers": [["tracker_id", "telegram_id", "full_name", "gender_scope", "role", "is_active"]],
        "Goals": [["goal_id", "participant_id", "goal_status"], ["G001", "P001", "active"]],
        "PlannedSteps": [
            [
                "step_id",
                "participant_id",
                "goal_id",
                "step_number",
                "step_title",
                "step_status",
                "closed_week_number",
                "closed_report_id",
                "closed_at",
            ],
            ["S001", "P001", "G001", "1", "Step one", "open", "", "", ""],
        ],
        "WeeklyReports": [
            [
                "weekly_report_id",
                "participant_id",
                "team_id",
                "goal_id",
                "week_number",
                "status_symbol",
                "status_code",
                "status_score",
                "report_text",
                "submitted_source",
            ]
        ],
        "WeeklyReportSteps": [
            ["id", "weekly_report_id", "participant_id", "step_id", "relation_type", "created_at"]
        ],
        "WeeklyFocus": [
            [
                "focus_id",
                "participant_id",
                "goal_id",
                "step_id",
                "week_number",
                "week_start_date",
                "week_end_date",
                "focus_status",
                "selected_at",
                "updated_at",
            ]
        ],
        "Insights": [
            [
                "insight_id",
                "participant_id",
                "goal_id",
                "week_number",
                "insight_scope",
                "insight_title",
                "insight_date",
                "insight_text",
                "transcription_text",
                "audio_file_path",
                "audio_deleted_at",
                "created_by_id",
                "created_by_role",
                "created_at",
            ]
        ],
    }
    sheets.update(overrides)
    return sheets


def minimal_challenge_flows_sheets(**overrides: list[list[object]]) -> dict[str, list[list[object]]]:
    sheets: dict[str, list[list[object]]] = {
        "ChallengeFlows": [
            [
                "flow_id",
                "flow_name",
                "flow_status",
                "kickoff_meeting_at",
                "registration_opens_at",
                "registration_closes_at",
                "data_collection_due_at",
                "bot_invite_at",
                "challenge_start_date",
                "goal_setup_start_date",
                "goal_setup_end_date",
                "steps_setup_start_date",
                "steps_setup_end_date",
                "week_01_start_date",
                "week_08_end_date",
                "final_summary_start_date",
                "final_summary_end_date",
                "expected_participant_count",
                "actual_participant_count",
                "active_team_count",
                "created_at",
                "updated_at",
            ],
            [
                "test-live-2026",
                "Test live flow",
                "active",
                "2026-05-23T10:00:00+05:00",
                "2026-05-23T10:00:00+05:00",
                "2026-05-30T10:00:00+05:00",
                "2026-05-25T10:00:00+05:00",
                "2026-05-25T12:00:00+05:00",
                "2026-05-25",
                "2026-05-25",
                "2026-05-31",
                "2026-06-01",
                "2026-06-07",
                "2026-06-08",
                "2026-08-02",
                "2026-08-03",
                "2026-08-06",
                "1",
                "1",
                "1",
                "2026-05-20T10:00:00+05:00",
                "2026-05-20T10:00:00+05:00",
            ],
        ]
    }
    sheets.update(overrides)
    return sheets
