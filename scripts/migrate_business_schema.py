"""Add required business-sheet headers without changing existing cells."""

from __future__ import annotations

import os

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


REQUIRED_HEADERS = {
    "Participants": (
        "bot_started_at", "consent_status", "flow_id",
        "last_stage_updated_at", "onboarding_completed_at", "participant_stage",
    ),
    "Teams": ("flow_id",),
    "PlannedSteps": (
        "step_number", "step_title", "step_description", "step_metric",
        "updated_at", "created_at",
    ),
    "WeeklyReportSteps": ("metric_status", "metric_result_text"),
}


def main() -> None:
    spreadsheet_id = os.environ["GOOGLE_SHEETS_ID"]
    credentials = Credentials.from_service_account_file(
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=("https://www.googleapis.com/auth/spreadsheets",),
    )
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    metadata = sheets.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets.properties(sheetId,title,gridProperties.columnCount)",
    ).execute()
    properties = {
        item["properties"]["title"]: item["properties"]
        for item in metadata.get("sheets", [])
    }
    missing_sheets = [name for name in REQUIRED_HEADERS if name not in properties]
    if missing_sheets:
        raise SystemExit(f"Missing required sheets: {missing_sheets}")

    plans = _migration_plans(sheets, spreadsheet_id)
    requests = _migration_requests(plans, properties)
    if requests:
        sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": requests}
        ).execute()
    _verify(sheets, spreadsheet_id, plans)


def _migration_plans(sheets, spreadsheet_id: str) -> list[tuple[str, list[str], int, int]]:
    plans = []
    for sheet_name, required_headers in REQUIRED_HEADERS.items():
        response = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'",
            valueRenderOption="FORMULA",
        ).execute()
        rows = response.get("values") or [[]]
        headers = list(rows[0])
        missing = [header for header in required_headers if header not in headers]
        if not missing:
            print(f"SCHEMA_OK sheet={sheet_name} added=0")
            continue
        start = max(len(headers), max((len(row) for row in rows), default=0))
        plans.append((sheet_name, missing, start, start + len(missing)))
    return plans


def _migration_requests(plans, properties) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for sheet_name, missing, start, end in plans:
        sheet_id = properties[sheet_name]["sheetId"]
        column_count = properties[sheet_name]["gridProperties"]["columnCount"]
        if end > column_count:
            requests.append({"appendDimension": {
                "sheetId": sheet_id, "dimension": "COLUMNS", "length": end - column_count,
            }})
        requests.append({"updateCells": {
            "range": {
                "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                "startColumnIndex": start, "endColumnIndex": end,
            },
            "rows": [{"values": [
                {"userEnteredValue": {"stringValue": header}} for header in missing
            ]}],
            "fields": "userEnteredValue",
        }})
        if start > 0:
            requests.append({"copyPaste": {
                "source": {
                    "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": start - 1, "endColumnIndex": start,
                },
                "destination": {
                    "sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": start, "endColumnIndex": end,
                },
                "pasteType": "PASTE_FORMAT", "pasteOrientation": "NORMAL",
            }})
    return requests


def _verify(sheets, spreadsheet_id: str, plans) -> None:
    for sheet_name, missing, _start, _end in plans:
        verified = sheets.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!1:1",
        ).execute().get("values", [[]])[0]
        absent = [header for header in REQUIRED_HEADERS[sheet_name] if header not in verified]
        if absent:
            raise SystemExit(f"Schema verification failed for {sheet_name}: {absent}")
        print(f"SCHEMA_OK sheet={sheet_name} added={len(missing)}")


if __name__ == "__main__":
    main()
