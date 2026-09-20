from __future__ import annotations

from scripts import migrate_business_schema as migration


class _Request:
    def __init__(self, result=None, action=None):
        self._result = result
        self._action = action

    def execute(self):
        if self._action:
            self._action()
        return self._result or {}


class _Values:
    def __init__(self, api):
        self.api = api

    def get(self, *, spreadsheetId, range, valueRenderOption=None):
        del spreadsheetId, valueRenderOption
        sheet_name = range.split("'", 2)[1]
        return _Request({"values": [self.api.headers[sheet_name]]})


class _Spreadsheets:
    def __init__(self, api):
        self.api = api

    def values(self):
        return _Values(self.api)

    def get(self, **_kwargs):
        sheets = [
            {"properties": {
                "sheetId": index, "title": name,
                "gridProperties": {"columnCount": max(20, len(headers))},
            }}
            for index, (name, headers) in enumerate(self.api.headers.items(), start=1)
        ]
        return _Request({"sheets": sheets})

    def batchUpdate(self, *, spreadsheetId, body):
        del spreadsheetId

        def apply():
            id_to_name = {index: name for index, name in enumerate(self.api.headers, start=1)}
            for request in body["requests"]:
                update = request.get("updateCells")
                if not update:
                    continue
                name = id_to_name[update["range"]["sheetId"]]
                values = update["rows"][0]["values"]
                self.api.headers[name].extend(
                    value["userEnteredValue"]["stringValue"] for value in values
                )
            self.api.batch_calls += 1

        return _Request(action=apply)


class _SheetsApi:
    def __init__(self, headers):
        self.headers = {name: list(values) for name, values in headers.items()}
        self.batch_calls = 0
        self._spreadsheets = _Spreadsheets(self)

    def spreadsheets(self):
        return self._spreadsheets


def test_business_schema_migration_adds_missing_headers_and_second_run_is_noop(
    monkeypatch,
) -> None:
    api = _SheetsApi({name: ["existing"] for name in migration.REQUIRED_HEADERS})
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheet-id")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/private/credentials.json")
    monkeypatch.setattr(
        migration.Credentials, "from_service_account_file",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(migration, "build", lambda *_args, **_kwargs: api)

    migration.main()

    assert api.batch_calls == 1
    for name, required in migration.REQUIRED_HEADERS.items():
        assert api.headers[name] == ["existing", *required]

    migration.main()
    assert api.batch_calls == 1


def test_business_schema_migration_fails_before_write_when_sheet_is_missing(
    monkeypatch,
) -> None:
    headers = {name: ["existing"] for name in migration.REQUIRED_HEADERS}
    del headers["WeeklyReportSteps"]
    api = _SheetsApi(headers)
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheet-id")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/private/credentials.json")
    monkeypatch.setattr(
        migration.Credentials, "from_service_account_file",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(migration, "build", lambda *_args, **_kwargs: api)

    import pytest
    with pytest.raises(SystemExit, match="Missing required sheets"):
        migration.main()
    assert api.batch_calls == 0
