"""Google Sheets boundary, live adapter, and fake in-memory implementation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol


SheetRow = dict[str, object]


class GoogleSheetsError(RuntimeError):
    """Raised when the live Google Sheets adapter cannot complete an operation."""


class GoogleSheetsSchemaError(GoogleSheetsError):
    """Raised when required tabs or columns are missing."""


class SheetsGateway(Protocol):
    def list_participants(self) -> list[SheetRow]:
        """Return all participant rows for scheduler selection."""

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        """Find a participant business row by Telegram ID."""

    def find_participant_in_flow(self, flow_id: str, telegram_id: int) -> SheetRow | None:
        """Find a participant by Telegram ID inside one challenge flow."""

    def append_participant(self, row: SheetRow) -> None:
        """Append a completed self-registration business row."""

    def get_participant(self, participant_id: str) -> SheetRow | None:
        """Find a participant business row by stable participant ID."""

    def list_participants_by_team(self, team_id: str) -> list[SheetRow]:
        """Return participant rows scoped to one team."""

    def list_teams(self) -> list[SheetRow]:
        """Return team rows used to resolve captain/tracker recipients."""

    def get_tracker(self, tracker_id: str) -> SheetRow | None:
        """Return one tracker row by stable tracker ID."""

    def list_trackers(self) -> list[SheetRow]:
        """Return tracker rows for report recipient planning."""

    def list_challenge_flows(self) -> list[SheetRow]:
        """Return configured challenge flows."""

    def list_flow_schedule(self) -> list[SheetRow]:
        """Return per-flow scheduled events."""

    def get_active_challenge_flow(self) -> SheetRow | None:
        """Return the active challenge flow row when available."""

    def mark_participant_bot_started(self, participant_id: str, *, started_at: str) -> None:
        """Persist first bot start metadata for an expected participant."""

    def update_participant_consent(
        self,
        participant_id: str,
        *,
        consent_given: bool,
        consent_given_at: str,
    ) -> None:
        """Persist participant consent fields to the business storage."""

    def get_active_goal(self, participant_id: str) -> SheetRow | None:
        """Return the participant's active goal row when available."""

    def list_planned_steps(self, participant_id: str, goal_id: str) -> list[SheetRow]:
        """Return planned steps scoped to the participant and goal."""

    def list_weekly_status_history(self, participant_id: str) -> list[SheetRow]:
        """Return weekly report/status rows scoped to the participant."""

    def append_weekly_report(self, row: SheetRow) -> None:
        """Append a final weekly report row to the business storage."""

    def find_weekly_report(self, participant_id: str, *, week_number: int) -> SheetRow | None:
        """Find one weekly report for a participant/week if it already exists."""

    def find_weekly_report_for_step(
        self,
        participant_id: str,
        *,
        step_id: str,
    ) -> SheetRow | None:
        """Find the final report linked to a planned step when it exists."""

    def get_weekly_report(self, weekly_report_id: str) -> SheetRow | None:
        """Return one weekly report by stable report ID."""

    def update_weekly_report_text(
        self,
        weekly_report_id: str,
        *,
        report_text: str,
        transcription_text: str,
        audio_file_path: str,
        updated_at: str,
    ) -> None:
        """Update editable weekly report text fields without changing original submission time."""

    def append_weekly_report_step(self, row: SheetRow) -> None:
        """Append a final weekly report to planned-step relation row."""

    def close_planned_steps(
        self,
        participant_id: str,
        goal_id: str,
        step_ids: Sequence[str],
        *,
        closed_week_number: int,
        closed_report_id: str,
        closed_at: str,
    ) -> None:
        """Mark selected participant planned steps as closed in business storage."""

    def append_insight(self, row: SheetRow) -> None:
        """Append a final insight row to the business storage."""

    def list_insights_for_participant(self, participant_id: str) -> list[SheetRow]:
        """Return final insight rows scoped to one participant."""

    def get_participant_insight(self, participant_id: str, insight_id: str) -> SheetRow | None:
        """Return one participant-scoped insight row when available."""

    def list_weekly_reports(self) -> list[SheetRow]:
        """Return weekly report rows for tests or future readers."""

    def list_weekly_report_steps(self) -> list[SheetRow]:
        """Return weekly report step relation rows for tests or future readers."""

    def list_insights(self) -> list[SheetRow]:
        """Return insight rows for tests or future readers."""

    def list_goals(self) -> list[SheetRow]:
        """Return all goal rows for report aggregation."""

    def list_planned_steps_all(self) -> list[SheetRow]:
        """Return all planned step rows for report aggregation."""

    def list_weekly_reports_for_week(self, week_number: int) -> list[SheetRow]:
        """Return final weekly report rows for one week."""

    def list_weekly_report_steps_all(self) -> list[SheetRow]:
        """Return all weekly report step relation rows for report aggregation."""

    def find_weekly_focus(
        self,
        participant_id: str,
        *,
        week_number: int,
    ) -> SheetRow | None:
        """Find the participant's selected focus step for one week."""

    def append_weekly_focus(self, row: SheetRow) -> None:
        """Append a weekly focus business row."""

    def list_weekly_focus_for_week(self, week_number: int) -> list[SheetRow]:
        """Return weekly focus rows for reports."""

    def list_insights_for_week(self, week_number: int) -> list[SheetRow]:
        """Return final insight rows for one week."""


REQUIRED_CHALLENGE_FLOW_COLUMNS = frozenset(
    {
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
    }
)


REQUIRED_SHEET_COLUMNS: dict[str, frozenset[str]] = {
    "Participants": frozenset(
        {
            "flow_id",
            "participant_id",
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "team_id",
            "team_name",
            "captain_id",
            "tracker_id",
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
        }
    ),
    "Teams": frozenset({"flow_id", "team_id", "team_name", "gender", "captain_id", "tracker_id", "is_active"}),
    "Trackers": frozenset({"tracker_id", "telegram_id", "full_name", "gender_scope", "role", "is_active"}),
    "Goals": frozenset({"goal_id", "participant_id", "goal_status"}),
    "PlannedSteps": frozenset(
        {
            "step_id",
            "participant_id",
            "goal_id",
            "step_status",
            "closed_week_number",
            "closed_report_id",
            "closed_at",
        }
    ),
    "WeeklyReports": frozenset(
        {
            "weekly_report_id",
            "participant_id",
            "team_id",
            "goal_id",
            "week_number",
            "status_code",
            "status_symbol",
            "status_score",
            "submitted_source",
        }
    ),
    "WeeklyReportSteps": frozenset(
        {"id", "weekly_report_id", "participant_id", "step_id", "relation_type", "created_at"}
    ),
    "WeeklyFocus": frozenset(
        {
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
        }
    ),
    "Insights": frozenset(
        {
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
        }
    ),
}

REQUIRED_CHALLENGE_FLOWS_SHEET_COLUMNS: dict[str, frozenset[str]] = {
    "ChallengeFlows": REQUIRED_CHALLENGE_FLOW_COLUMNS,
}


@dataclass(frozen=True)
class GoogleSheetsGateway:
    service: object
    spreadsheet_id: str

    def list_participants(self) -> list[SheetRow]:
        return self._list_rows("Participants")

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        for row in self.list_participants():
            if row.get("telegram_id") == telegram_id:
                return row
        return None

    def find_participant_in_flow(self, flow_id: str, telegram_id: int) -> SheetRow | None:
        for row in self.list_participants():
            if row.get("flow_id") == flow_id and row.get("telegram_id") == telegram_id:
                return row
        return None

    def append_participant(self, row: SheetRow) -> None:
        self._append_row("Participants", row)

    def get_participant(self, participant_id: str) -> SheetRow | None:
        for row in self.list_participants():
            if row.get("participant_id") == participant_id:
                return row
        return None

    def list_participants_by_team(self, team_id: str) -> list[SheetRow]:
        return [row for row in self.list_participants() if row.get("team_id") == team_id]

    def list_teams(self) -> list[SheetRow]:
        return self._list_rows("Teams")

    def get_tracker(self, tracker_id: str) -> SheetRow | None:
        for row in self.list_trackers():
            if row.get("tracker_id") == tracker_id:
                return row
        return None

    def list_trackers(self) -> list[SheetRow]:
        return self._list_rows("Trackers")

    def list_challenge_flows(self) -> list[SheetRow]:
        return self._list_rows("ChallengeFlows")

    def list_flow_schedule(self) -> list[SheetRow]:
        return self._list_rows("FlowSchedule")

    def get_active_challenge_flow(self) -> SheetRow | None:
        for row in self.list_challenge_flows():
            if str(row.get("flow_status", "")).strip().lower() == "active":
                return row
        return None

    def mark_participant_bot_started(self, participant_id: str, *, started_at: str) -> None:
        headers, rows = self._table("Participants")
        participant_id_index = _header_index(headers, "participant_id")
        bot_started_index = _header_index(headers, "bot_started_at")
        stage_index = _header_index(headers, "participant_stage")
        updated_index = _header_index(headers, "last_stage_updated_at")
        for offset, row in enumerate(rows, start=2):
            padded = _pad_row(row, len(headers))
            if padded[participant_id_index] != participant_id:
                continue
            if not str(padded[bot_started_index]).strip():
                padded[bot_started_index] = started_at
            if not str(padded[stage_index]).strip() or str(padded[stage_index]).strip() in {"invited", "pre_start"}:
                padded[stage_index] = "onboarding"
            padded[updated_index] = started_at
            self._update_row("Participants", offset, padded)
            return
        raise KeyError(f"Participant not found: {participant_id}")

    def update_participant_consent(
        self,
        participant_id: str,
        *,
        consent_given: bool,
        consent_given_at: str,
    ) -> None:
        headers, rows = self._table("Participants")
        participant_id_index = _header_index(headers, "participant_id")
        consent_index = _header_index(headers, "consent_given")
        consent_at_index = _header_index(headers, "consent_given_at")
        consent_status_index = _header_index(headers, "consent_status")
        stage_index = _header_index(headers, "participant_stage")
        onboarding_completed_index = _header_index(headers, "onboarding_completed_at")
        updated_index = _header_index(headers, "last_stage_updated_at")
        for offset, row in enumerate(rows, start=2):
            padded = _pad_row(row, len(headers))
            if padded[participant_id_index] != participant_id:
                continue
            padded[consent_index] = "TRUE" if consent_given else "FALSE"
            padded[consent_at_index] = consent_given_at
            padded[consent_status_index] = "accepted" if consent_given else "declined"
            padded[stage_index] = "goal_setup" if consent_given else "declined"
            if consent_given and not str(padded[onboarding_completed_index]).strip():
                padded[onboarding_completed_index] = consent_given_at
            padded[updated_index] = consent_given_at
            self._update_row("Participants", offset, padded)
            return
        raise KeyError(f"Participant not found: {participant_id}")

    def get_active_goal(self, participant_id: str) -> SheetRow | None:
        for row in self.list_goals():
            if row.get("participant_id") == participant_id and row.get("goal_status") == "active":
                return row
        return None

    def list_planned_steps(self, participant_id: str, goal_id: str) -> list[SheetRow]:
        return [
            row
            for row in self._list_rows("PlannedSteps")
            if row.get("participant_id") == participant_id and row.get("goal_id") == goal_id
        ]

    def list_weekly_status_history(self, participant_id: str) -> list[SheetRow]:
        return [
            row
            for row in self.list_weekly_reports()
            if row.get("participant_id") == participant_id
        ]

    def append_weekly_report(self, row: SheetRow) -> None:
        self._append_row("WeeklyReports", row)

    def find_weekly_report(self, participant_id: str, *, week_number: int) -> SheetRow | None:
        for row in self.list_weekly_reports():
            if row.get("participant_id") == participant_id and row.get("week_number") == week_number:
                return row
        return None

    def find_weekly_report_for_step(
        self,
        participant_id: str,
        *,
        step_id: str,
    ) -> SheetRow | None:
        report_ids = {
            str(row.get("weekly_report_id"))
            for row in self.list_weekly_report_steps()
            if row.get("participant_id") == participant_id and row.get("step_id") == step_id
        }
        for row in self.list_weekly_reports():
            if row.get("participant_id") == participant_id and str(row.get("weekly_report_id")) in report_ids:
                return row
        return None

    def get_weekly_report(self, weekly_report_id: str) -> SheetRow | None:
        for row in self.list_weekly_reports():
            if row.get("weekly_report_id") == weekly_report_id:
                return row
        return None

    def update_weekly_report_text(
        self,
        weekly_report_id: str,
        *,
        report_text: str,
        transcription_text: str,
        audio_file_path: str,
        updated_at: str,
    ) -> None:
        headers, rows = self._table("WeeklyReports")
        report_id_index = _header_index(headers, "weekly_report_id")
        report_text_index = _header_index(headers, "report_text")
        transcription_index = _header_index(headers, "transcription_text")
        audio_index = _header_index(headers, "audio_file_path")
        updated_at_index = _header_index(headers, "updated_at")
        for offset, row in enumerate(rows, start=2):
            padded = _pad_row(row, len(headers))
            if padded[report_id_index] == weekly_report_id:
                padded[report_text_index] = report_text
                padded[transcription_index] = transcription_text
                padded[audio_index] = audio_file_path
                padded[updated_at_index] = updated_at
                self._update_row("WeeklyReports", offset, padded)
                return
        raise KeyError(f"Weekly report not found: {weekly_report_id}")

    def append_weekly_report_step(self, row: SheetRow) -> None:
        self._append_row("WeeklyReportSteps", row)

    def close_planned_steps(
        self,
        participant_id: str,
        goal_id: str,
        step_ids: Sequence[str],
        *,
        closed_week_number: int,
        closed_report_id: str,
        closed_at: str,
    ) -> None:
        headers, rows = self._table("PlannedSteps")
        row_by_step_id: dict[str, tuple[int, list[object]]] = {}
        for offset, row in enumerate(rows, start=2):
            row_data = _row_from_values(headers, row)
            if row_data.get("participant_id") == participant_id and row_data.get("goal_id") == goal_id:
                step_id = row_data.get("step_id")
                if isinstance(step_id, str):
                    row_by_step_id[step_id] = (offset, _pad_row(row, len(headers)))

        missing_step_ids = [step_id for step_id in step_ids if step_id not in row_by_step_id]
        if missing_step_ids:
            raise KeyError(f"Planned steps not found for participant/goal: {', '.join(missing_step_ids)}")

        status_index = _header_index(headers, "step_status")
        week_index = _header_index(headers, "closed_week_number")
        report_index = _header_index(headers, "closed_report_id")
        closed_at_index = _header_index(headers, "closed_at")
        for step_id in step_ids:
            offset, row = row_by_step_id[step_id]
            row[status_index] = "closed"
            row[week_index] = closed_week_number
            row[report_index] = closed_report_id
            row[closed_at_index] = closed_at
            self._update_row("PlannedSteps", offset, row)

    def append_insight(self, row: SheetRow) -> None:
        self._append_row("Insights", row)

    def list_insights_for_participant(self, participant_id: str) -> list[SheetRow]:
        return [
            row
            for row in self.list_insights()
            if row.get("participant_id") == participant_id
        ]

    def get_participant_insight(self, participant_id: str, insight_id: str) -> SheetRow | None:
        for row in self.list_insights_for_participant(participant_id):
            if row.get("insight_id") == insight_id:
                return row
        return None

    def list_weekly_reports(self) -> list[SheetRow]:
        return self._list_rows("WeeklyReports")

    def list_weekly_report_steps(self) -> list[SheetRow]:
        return self._list_rows("WeeklyReportSteps")

    def list_insights(self) -> list[SheetRow]:
        return self._list_rows("Insights")

    def list_goals(self) -> list[SheetRow]:
        return self._list_rows("Goals")

    def list_planned_steps_all(self) -> list[SheetRow]:
        return self._list_rows("PlannedSteps")

    def list_weekly_reports_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            row
            for row in self.list_weekly_reports()
            if row.get("week_number") == week_number
        ]

    def list_weekly_report_steps_all(self) -> list[SheetRow]:
        return self.list_weekly_report_steps()

    def find_weekly_focus(
        self,
        participant_id: str,
        *,
        week_number: int,
    ) -> SheetRow | None:
        for row in self._list_rows("WeeklyFocus"):
            if row.get("participant_id") == participant_id and row.get("week_number") == week_number:
                return row
        return None

    def append_weekly_focus(self, row: SheetRow) -> None:
        self._append_row("WeeklyFocus", row)

    def list_weekly_focus_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            row
            for row in self._list_rows("WeeklyFocus")
            if row.get("week_number") == week_number
        ]

    def list_insights_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            row
            for row in self.list_insights()
            if row.get("week_number") == week_number
        ]

    def _list_rows(self, sheet_name: str) -> list[SheetRow]:
        headers, rows = self._table(sheet_name)
        return [_row_from_values(headers, row) for row in rows]

    def _table(self, sheet_name: str) -> tuple[list[str], list[list[object]]]:
        values = _execute(
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=_sheet_range(sheet_name))
        ).get("values", [])
        if not isinstance(values, list) or not values:
            return [], []
        headers = [str(value) for value in values[0]]
        rows = [list(row) for row in values[1:] if isinstance(row, list)]
        return headers, rows

    def _append_row(self, sheet_name: str, row: SheetRow) -> None:
        headers, _rows = self._table(sheet_name)
        if not headers:
            raise GoogleSheetsSchemaError(f"Sheet {sheet_name} has no header row")
        values = [_value_for_header(row, header) for header in headers]
        _execute(
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=_sheet_range(sheet_name),
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [values]},
            )
        )

    def _update_row(self, sheet_name: str, row_number: int, values: list[object]) -> None:
        _execute(
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{_sheet_range(sheet_name)}!A{row_number}",
                valueInputOption="USER_ENTERED",
                body={"values": [values]},
            )
        )


def validate_required_schema(service: object, *, spreadsheet_id: str) -> None:
    _validate_schema(service, spreadsheet_id=spreadsheet_id, required_sheet_columns=REQUIRED_SHEET_COLUMNS)


def validate_challenge_flows_schema(service: object, *, spreadsheet_id: str) -> None:
    _validate_schema(
        service,
        spreadsheet_id=spreadsheet_id,
        required_sheet_columns=REQUIRED_CHALLENGE_FLOWS_SHEET_COLUMNS,
    )


def _validate_schema(
    service: object,
    *,
    spreadsheet_id: str,
    required_sheet_columns: dict[str, frozenset[str]],
) -> None:
    spreadsheet = _execute(service.spreadsheets().get(spreadsheetId=spreadsheet_id))
    sheets = spreadsheet.get("sheets", [])
    if not isinstance(sheets, list):
        raise GoogleSheetsSchemaError("Google Sheets schema validation failed: sheets metadata missing")

    available_titles = {
        str(sheet.get("properties", {}).get("title"))
        for sheet in sheets
        if isinstance(sheet, dict) and isinstance(sheet.get("properties"), dict)
    }
    missing_tabs = sorted(set(required_sheet_columns) - available_titles)
    if missing_tabs:
        raise GoogleSheetsSchemaError(f"Missing required Google Sheets tabs: {', '.join(missing_tabs)}")

    missing_columns: list[str] = []
    for sheet_name, required_columns in required_sheet_columns.items():
        values = _execute(
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=_sheet_range(sheet_name))
        ).get("values", [])
        headers = {str(value) for value in values[0]} if isinstance(values, list) and values else set()
        missing = sorted(required_columns - headers)
        if missing:
            missing_columns.append(f"{sheet_name}: {', '.join(missing)}")
    if missing_columns:
        raise GoogleSheetsSchemaError(
            "Missing required Google Sheets columns: " + "; ".join(missing_columns)
        )


class FakeSheetsGateway:
    def __init__(
        self,
        *,
        participants: Iterable[SheetRow] = (),
        teams: Iterable[SheetRow] = (),
        trackers: Iterable[SheetRow] = (),
        goals: Iterable[SheetRow] = (),
        planned_steps: Iterable[SheetRow] = (),
        weekly_reports: Iterable[SheetRow] = (),
        weekly_report_steps: Iterable[SheetRow] = (),
        weekly_focus: Iterable[SheetRow] = (),
        insights: Iterable[SheetRow] = (),
        challenge_flows: Iterable[SheetRow] = (),
        flow_schedule: Iterable[SheetRow] = (),
    ) -> None:
        self._participants = _copy_rows(participants)
        self._teams = _copy_rows(teams)
        self._trackers = _copy_rows(trackers)
        self._goals = _copy_rows(goals)
        self._planned_steps = _copy_rows(planned_steps)
        self._weekly_reports = _copy_rows(weekly_reports)
        self._weekly_report_steps = _copy_rows(weekly_report_steps)
        self._weekly_focus = _copy_rows(weekly_focus)
        self._insights = _copy_rows(insights)
        self._challenge_flows = _copy_rows(challenge_flows)
        self._flow_schedule = _copy_rows(flow_schedule)

    def list_participants(self) -> list[SheetRow]:
        return [dict(row) for row in self._participants]

    def find_participant_by_telegram_id(self, telegram_id: int) -> SheetRow | None:
        for row in self._participants:
            if row.get("telegram_id") == telegram_id:
                return dict(row)
        return None

    def find_participant_in_flow(self, flow_id: str, telegram_id: int) -> SheetRow | None:
        for row in self._participants:
            if row.get("flow_id") == flow_id and row.get("telegram_id") == telegram_id:
                return dict(row)
        return None

    def append_participant(self, row: SheetRow) -> None:
        if self.find_participant_in_flow(str(row.get("flow_id", "")), int(row.get("telegram_id", 0))):
            return
        self._participants.append(dict(row))

    def get_participant(self, participant_id: str) -> SheetRow | None:
        for row in self._participants:
            if row.get("participant_id") == participant_id:
                return dict(row)
        return None

    def list_participants_by_team(self, team_id: str) -> list[SheetRow]:
        return [dict(row) for row in self._participants if row.get("team_id") == team_id]

    def list_teams(self) -> list[SheetRow]:
        return [dict(row) for row in self._teams]

    def get_tracker(self, tracker_id: str) -> SheetRow | None:
        for row in self._trackers:
            if row.get("tracker_id") == tracker_id:
                return dict(row)
        return None

    def list_trackers(self) -> list[SheetRow]:
        return [dict(row) for row in self._trackers]

    def list_challenge_flows(self) -> list[SheetRow]:
        return [dict(row) for row in self._challenge_flows]

    def list_flow_schedule(self) -> list[SheetRow]:
        return [dict(row) for row in self._flow_schedule]

    def get_active_challenge_flow(self) -> SheetRow | None:
        for row in self._challenge_flows:
            if str(row.get("flow_status", "")).strip().lower() == "active":
                return dict(row)
        return None

    def mark_participant_bot_started(self, participant_id: str, *, started_at: str) -> None:
        for row in self._participants:
            if row.get("participant_id") == participant_id:
                row.setdefault("bot_started_at", started_at)
                if not row.get("bot_started_at"):
                    row["bot_started_at"] = started_at
                stage = str(row.get("participant_stage", "")).strip()
                if stage in {"", "invited", "pre_start"}:
                    row["participant_stage"] = "onboarding"
                row["last_stage_updated_at"] = started_at
                return
        raise KeyError(f"Participant not found: {participant_id}")

    def update_participant_consent(
        self,
        participant_id: str,
        *,
        consent_given: bool,
        consent_given_at: str,
    ) -> None:
        for row in self._participants:
            if row.get("participant_id") == participant_id:
                row["consent_given"] = consent_given
                row["consent_given_at"] = consent_given_at
                row["consent_status"] = "accepted" if consent_given else "declined"
                row["participant_stage"] = "goal_setup" if consent_given else "declined"
                if consent_given and not row.get("onboarding_completed_at"):
                    row["onboarding_completed_at"] = consent_given_at
                row["last_stage_updated_at"] = consent_given_at
                return
        raise KeyError(f"Participant not found: {participant_id}")

    def get_active_goal(self, participant_id: str) -> SheetRow | None:
        for row in self._goals:
            if row.get("participant_id") == participant_id and row.get("goal_status") == "active":
                return dict(row)
        return None

    def list_planned_steps(self, participant_id: str, goal_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._planned_steps
            if row.get("participant_id") == participant_id and row.get("goal_id") == goal_id
        ]

    def list_weekly_status_history(self, participant_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._weekly_reports
            if row.get("participant_id") == participant_id
        ]

    def append_weekly_report(self, row: SheetRow) -> None:
        self._weekly_reports.append(dict(row))

    def find_weekly_report(self, participant_id: str, *, week_number: int) -> SheetRow | None:
        for row in self._weekly_reports:
            if row.get("participant_id") == participant_id and row.get("week_number") == week_number:
                return dict(row)
        return None

    def find_weekly_report_for_step(
        self,
        participant_id: str,
        *,
        step_id: str,
    ) -> SheetRow | None:
        report_ids = {
            str(row.get("weekly_report_id"))
            for row in self._weekly_report_steps
            if row.get("participant_id") == participant_id and row.get("step_id") == step_id
        }
        for row in self._weekly_reports:
            if row.get("participant_id") == participant_id and str(row.get("weekly_report_id")) in report_ids:
                return dict(row)
        return None

    def get_weekly_report(self, weekly_report_id: str) -> SheetRow | None:
        for row in self._weekly_reports:
            if row.get("weekly_report_id") == weekly_report_id:
                return dict(row)
        return None

    def update_weekly_report_text(
        self,
        weekly_report_id: str,
        *,
        report_text: str,
        transcription_text: str,
        audio_file_path: str,
        updated_at: str,
    ) -> None:
        for row in self._weekly_reports:
            if row.get("weekly_report_id") == weekly_report_id:
                row["report_text"] = report_text
                row["transcription_text"] = transcription_text
                row["audio_file_path"] = audio_file_path
                row["updated_at"] = updated_at
                return
        raise KeyError(f"Weekly report not found: {weekly_report_id}")

    def append_weekly_report_step(self, row: SheetRow) -> None:
        self._weekly_report_steps.append(dict(row))

    def close_planned_steps(
        self,
        participant_id: str,
        goal_id: str,
        step_ids: Sequence[str],
        *,
        closed_week_number: int,
        closed_report_id: str,
        closed_at: str,
    ) -> None:
        matching_rows = [
            row
            for row in self._planned_steps
            if row.get("participant_id") == participant_id
            and row.get("goal_id") == goal_id
            and row.get("step_id") in step_ids
        ]
        found_step_ids = {str(row.get("step_id")) for row in matching_rows}
        missing_step_ids = [step_id for step_id in step_ids if step_id not in found_step_ids]
        if missing_step_ids:
            raise KeyError(f"Planned steps not found for participant/goal: {', '.join(missing_step_ids)}")

        for row in matching_rows:
            row["step_status"] = "closed"
            row["closed_week_number"] = closed_week_number
            row["closed_report_id"] = closed_report_id
            row["closed_at"] = closed_at

    def append_insight(self, row: SheetRow) -> None:
        self._insights.append(dict(row))

    def list_insights_for_participant(self, participant_id: str) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._insights
            if row.get("participant_id") == participant_id
        ]

    def get_participant_insight(self, participant_id: str, insight_id: str) -> SheetRow | None:
        for row in self._insights:
            if row.get("participant_id") == participant_id and row.get("insight_id") == insight_id:
                return dict(row)
        return None

    def list_weekly_reports(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_reports]

    def list_weekly_report_steps(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_report_steps]

    def list_insights(self) -> list[SheetRow]:
        return [dict(row) for row in self._insights]

    def list_goals(self) -> list[SheetRow]:
        return [dict(row) for row in self._goals]

    def list_planned_steps_all(self) -> list[SheetRow]:
        return [dict(row) for row in self._planned_steps]

    def list_weekly_reports_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._weekly_reports
            if row.get("week_number") == week_number
        ]

    def list_weekly_report_steps_all(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_report_steps]

    def find_weekly_focus(
        self,
        participant_id: str,
        *,
        week_number: int,
    ) -> SheetRow | None:
        for row in self._weekly_focus:
            if row.get("participant_id") == participant_id and row.get("week_number") == week_number:
                return dict(row)
        return None

    def append_weekly_focus(self, row: SheetRow) -> None:
        self._weekly_focus.append(dict(row))

    def list_weekly_focus_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._weekly_focus
            if row.get("week_number") == week_number
        ]

    def list_insights_for_week(self, week_number: int) -> list[SheetRow]:
        return [
            dict(row)
            for row in self._insights
            if row.get("week_number") == week_number
        ]


def _copy_rows(rows: Iterable[SheetRow]) -> list[SheetRow]:
    return [dict(row) for row in rows]


def _execute(request: object) -> dict[str, object]:
    try:
        payload = request.execute()
    except Exception as exc:
        raise GoogleSheetsError(f"Google Sheets request failed: {type(exc).__name__}") from exc
    if not isinstance(payload, dict):
        raise GoogleSheetsError("Google Sheets request failed: invalid response")
    return payload


def _sheet_range(sheet_name: str) -> str:
    return sheet_name


def _row_from_values(headers: Sequence[str], row: Sequence[object]) -> SheetRow:
    padded = _pad_row(row, len(headers))
    data = {header: _coerce_cell(padded[index]) for index, header in enumerate(headers)}
    _add_read_aliases(data)
    return data


def _pad_row(row: Sequence[object], length: int) -> list[object]:
    padded = list(row)
    if len(padded) < length:
        padded.extend("" for _ in range(length - len(padded)))
    return padded


def _coerce_cell(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.upper() == "TRUE":
        return True
    if text.upper() == "FALSE":
        return False
    if text == "":
        return ""
    try:
        if "." not in text:
            return int(text)
        parsed_float = float(text)
    except ValueError:
        return value
    return parsed_float


def _add_read_aliases(row: SheetRow) -> None:
    aliases = {
        "status_score": "score",
        "submitted_source": "flow_source",
        "id": "weekly_report_step_id",
        "relation_type": "relation_status",
    }
    for source, alias in aliases.items():
        if source in row and alias not in row:
            row[alias] = row[source]
    schedule_headers = {
        "ID события": "event_id",
        "ID потока": "flow_id",
        "Дата": "scheduled_date",
        "Время": "scheduled_time",
        "Часовой пояс": "scheduled_timezone",
        "День недели": "weekday_code",
        "Этап": "phase_code",
        "№ недели": "week_number",
        "Момент недели": "week_position",
        "Тип события": "event_type",
        "Получатель": "recipient_role",
        "Условие": "condition_code",
        "Текст сообщения / действие": "message_text",
        "Включено": "is_enabled",
        "Порядок": "sort_order",
        "Статус проверки": "validation_status",
        "Последняя проверка": "last_validated_at",
        "Комментарий": "notes",
    }
    for source, alias in schedule_headers.items():
        if source in row and alias not in row:
            row[alias] = row[source]


def _value_for_header(row: SheetRow, header: str) -> object:
    if header in row:
        return row[header]
    aliases = {
        "status_score": "score",
        "submitted_source": "flow_source",
        "id": "weekly_report_step_id",
        "relation_type": "relation_status",
    }
    alias = aliases.get(header)
    if alias is not None and alias in row:
        return row[alias]
    return ""


def _header_index(headers: Sequence[str], header: str) -> int:
    try:
        return list(headers).index(header)
    except ValueError as exc:
        raise GoogleSheetsSchemaError(f"Missing required Google Sheets column: {header}") from exc
