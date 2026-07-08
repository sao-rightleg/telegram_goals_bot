"""Scheduler job service contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReminderJobResult:
    sent_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0


@dataclass(frozen=True)
class WeekCloseResult:
    gray_created_count: int = 0
    existing_count: int = 0
    failed_count: int = 0
    notified_team_count: int = 0


@dataclass(frozen=True)
class SilentParticipant:
    participant_id: str
    team_id: str
    full_name: str
