"""Weekly report service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class WeeklyReportStatusDetails:
    code: str
    symbol: str
    score: int | float


class WeeklyReportStatus(Enum):
    GREEN = WeeklyReportStatusDetails(code="green", symbol="🟩", score=1)
    BLUE = WeeklyReportStatusDetails(code="blue", symbol="🟦", score=0.5)
    RED = WeeklyReportStatusDetails(code="red", symbol="🟥", score=0)

    @property
    def code(self) -> str:
        return self.value.code

    @property
    def symbol(self) -> str:
        return self.value.symbol

    @property
    def score(self) -> int | float:
        return self.value.score
