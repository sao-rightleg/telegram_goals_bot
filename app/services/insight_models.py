"""Insight flow service contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class InsightScope(str, Enum):
    CURRENT_WEEK = "current_week"


@dataclass(frozen=True)
class InsightListItem:
    insight_id: str
    insight_date: str
    title: str
    text_preview: str
    full_text: str | None = None


@dataclass(frozen=True)
class InsightPage:
    items: tuple[InsightListItem, ...]
    page_index: int
    page_size: int
    total_count: int

    @property
    def has_older(self) -> bool:
        return (self.page_index + 1) * self.page_size < self.total_count

    @property
    def has_newer(self) -> bool:
        return self.page_index > 0
