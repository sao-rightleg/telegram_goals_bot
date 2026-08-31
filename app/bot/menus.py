"""Role-aware Telegram menu definitions."""

from __future__ import annotations

from enum import Enum

from app.services.participant_models import MenuItem


class MenuAction(str, Enum):
    VIEW_GOAL = "view_goal"
    VIEW_STEPS = "view_steps"
    VIEW_PROGRESS = "view_progress"
    START_WEEKLY_REPORT = "start_weekly_report"
    VIEW_INSIGHTS = "view_insights"
    VIEW_TEAM = "view_team"
    CAPTAIN_MANUAL_REPORT = "captain_manual_report"
    VIEW_TEAM_REPORT = "view_team_report"


CONSENT_ACCEPT_CALLBACK = "consent:accept"
CONSENT_DECLINE_CALLBACK = "consent:decline"
CONSENT_DECLINE_CONFIRM_CALLBACK = "consent:decline_confirm"

MENU_CALLBACK_PREFIX = "menu:"

WEEKLY_REPORT_START_CALLBACK = "weekly:start"
WEEKLY_REPORT_START_STEP_CALLBACK_PREFIX = "weekly:start_step:"
WEEKLY_REPORT_EDIT_STEP_CALLBACK_PREFIX = "weekly:edit_step:"
WEEKLY_REPORT_STATUS_CALLBACK_PREFIX = "weekly:status:"
WEEKLY_REPORT_STEPS_CALLBACK_PREFIX = "weekly:steps:"
WEEKLY_REPORT_DONE_CALLBACK = "weekly:done"

WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX = "focus:select:"

INSIGHT_MENU_CALLBACK = "insight:menu"
INSIGHT_ADD_CALLBACK = "insight:add"
INSIGHT_LIST_CALLBACK_PREFIX = "insight:list:"
INSIGHT_FULL_TEXT_CALLBACK_PREFIX = "insight:full:"
INSIGHT_DONE_CALLBACK = "insight:done"
INSIGHT_SKIP_TITLE_CALLBACK = "insight:skip_title"
INSIGHT_CANCEL_CALLBACK = "insight:cancel"

CAPTAIN_TEAM_CALLBACK = "captain:team"
CAPTAIN_MANUAL_REPORT_CALLBACK_PREFIX = "captain:manual:"
CAPTAIN_STATUS_CALLBACK_PREFIX = "captain:status:"
CAPTAIN_STEPS_CALLBACK_PREFIX = "captain:steps:"
CAPTAIN_DONE_CALLBACK = "captain:done"


PARTICIPANT_MENU_ITEMS = (
    MenuItem(MenuAction.VIEW_GOAL, "🎯 Моя цель"),
    MenuItem(MenuAction.VIEW_STEPS, "📍 Мои шаги"),
    MenuItem(MenuAction.VIEW_PROGRESS, "📊 Мой прогресс"),
    MenuItem(MenuAction.START_WEEKLY_REPORT, "📝 Отчёт за неделю"),
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
