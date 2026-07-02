"""Role-aware Telegram menu definitions."""

from __future__ import annotations

from enum import Enum

from app.services.participant_models import MenuItem


class MenuAction(str, Enum):
    VIEW_GOAL = "view_goal"
    VIEW_STEPS = "view_steps"
    VIEW_PROGRESS = "view_progress"
    VIEW_INSIGHTS = "view_insights"
    VIEW_TEAM = "view_team"
    CAPTAIN_MANUAL_REPORT = "captain_manual_report"
    VIEW_TEAM_REPORT = "view_team_report"


PARTICIPANT_MENU_ITEMS = (
    MenuItem(MenuAction.VIEW_GOAL, "🎯 Моя цель"),
    MenuItem(MenuAction.VIEW_STEPS, "📍 Мои шаги"),
    MenuItem(MenuAction.VIEW_PROGRESS, "📊 Мой прогресс"),
    MenuItem(MenuAction.VIEW_INSIGHTS, "💡 Мои инсайты"),
)

CAPTAIN_ONLY_MENU_ITEMS = (
    MenuItem(MenuAction.VIEW_TEAM, "👥 Моя команда"),
    MenuItem(MenuAction.CAPTAIN_MANUAL_REPORT, "➕ Внести отчёт за участника"),
    MenuItem(MenuAction.VIEW_TEAM_REPORT, "📄 Отчёт команды"),
)

CAPTAIN_MENU_ITEMS = PARTICIPANT_MENU_ITEMS + CAPTAIN_ONLY_MENU_ITEMS

PARTICIPANT_MENU_LABELS = [item.label for item in PARTICIPANT_MENU_ITEMS]
CAPTAIN_MENU_LABELS = [item.label for item in CAPTAIN_MENU_ITEMS]


def build_role_menu(role: str) -> tuple[MenuItem, ...]:
    if role == "captain":
        return CAPTAIN_MENU_ITEMS
    return PARTICIPANT_MENU_ITEMS
