"""Participant core flow contracts."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TelegramUserContext:
    telegram_id: int
    chat_id: str
    username: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@dataclass(frozen=True)
class Participant:
    participant_id: str
    telegram_id: int
    username: str | None
    full_name: str
    role: str
    team_id: str | None
    team_name: str | None
    captain_id: str | None
    tracker_id: str | None
    status: str
    consent_given: bool
    consent_given_at: str | None = None


@dataclass(frozen=True)
class Goal:
    goal_id: str
    participant_id: str
    goal_title: str
    goal_description: str
    goal_value_amount: str | int | float | None
    goal_value_currency: str | None
    permission_condition: str
    goal_status: str


@dataclass(frozen=True)
class PlannedStep:
    step_id: str
    participant_id: str
    goal_id: str
    step_number: int
    step_title: str
    step_description: str
    step_status: str
    closed_week_number: int | None = None
    closed_at: str | None = None


@dataclass(frozen=True)
class WeeklyStatus:
    week_number: int
    status_symbol: str
    status_code: str
    submitted_at: str | None = None


@dataclass(frozen=True)
class MenuItem:
    action: str
    label: str


@dataclass(frozen=True)
class FlowResponse:
    chat_id: str
    text: str
    menu_items: tuple[MenuItem, ...] = field(default_factory=tuple)
    buttons: tuple[str, ...] = field(default_factory=tuple)
