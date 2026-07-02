"""Google Sheets boundary and fake in-memory implementation."""

from __future__ import annotations

from typing import Protocol


SheetRow = dict[str, object]


class SheetsGateway(Protocol):
    def append_weekly_report(self, row: SheetRow) -> None:
        """Append a final weekly report row to the business storage."""

    def append_insight(self, row: SheetRow) -> None:
        """Append a final insight row to the business storage."""

    def list_weekly_reports(self) -> list[SheetRow]:
        """Return weekly report rows for tests or future readers."""

    def list_insights(self) -> list[SheetRow]:
        """Return insight rows for tests or future readers."""


class FakeSheetsGateway:
    def __init__(self) -> None:
        self._weekly_reports: list[SheetRow] = []
        self._insights: list[SheetRow] = []

    def append_weekly_report(self, row: SheetRow) -> None:
        self._weekly_reports.append(dict(row))

    def append_insight(self, row: SheetRow) -> None:
        self._insights.append(dict(row))

    def list_weekly_reports(self) -> list[SheetRow]:
        return [dict(row) for row in self._weekly_reports]

    def list_insights(self) -> list[SheetRow]:
        return [dict(row) for row in self._insights]
