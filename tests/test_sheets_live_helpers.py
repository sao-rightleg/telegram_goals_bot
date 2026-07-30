from __future__ import annotations

from collections.abc import Iterable


class FakeSheetsService:
    def __init__(self, sheets: dict[str, list[list[object]]]) -> None:
        self.sheets = {name: [list(row) for row in rows] for name, rows in sheets.items()}
        self.appended: list[tuple[str, list[object]]] = []
        self.updated: list[tuple[str, list[list[object]]]] = []

    def spreadsheets(self) -> "FakeSheetsService":
        return self

    def values(self) -> "FakeSheetsService":
        return self

    def get_values(self, range_name: str) -> list[list[object]]:
        title = _sheet_title(range_name)
        return [list(row) for row in self.sheets.get(title, [])]

    def get(self, *, spreadsheetId: str, range: str | None = None):  # type: ignore[override]
        if range is None:
            return _Executable(
                {
                    "sheets": [
                        {"properties": {"title": title}}
                        for title in self.sheets
                    ]
                }
            )
        return _Executable({"values": self.get_values(range)})

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
        self.sheets.setdefault(title, []).extend(values)
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
        rows = self.sheets.setdefault(title, [])
        for offset, row in enumerate(values):
            index = start_row + offset - 1
            while len(rows) <= index:
                rows.append([])
            rows[index] = list(row)
        self.updated.append((range, values))
        return _Executable({"updatedRows": len(values)})


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
                "participant_id",
                "telegram_id",
                "username",
                "full_name",
                "team_id",
                "role",
                "status",
                "consent_given",
                "consent_given_at",
            ],
            ["P001", "1001", "p001", "Participant One", "T001", "participant", "active", "FALSE", ""],
        ],
        "Teams": [["team_id", "team_name", "gender", "captain_id", "tracker_id", "is_active"]],
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
