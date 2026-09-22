"""Safe, structured diagnostics for operational error notifications."""

from __future__ import annotations

from enum import Enum


class ActionDiagnosticKind(str, Enum):
    GOAL_FLOW_UNAVAILABLE = "goal_flow_unavailable"
    GOAL_STAGE_CLOSED = "goal_stage_closed"
    GOAL_PARTICIPANT_NOT_FOUND = "goal_participant_not_found"
    GOAL_CONSENT_MISSING = "goal_consent_missing"
    GOAL_PARTICIPANT_INACTIVE = "goal_participant_inactive"
    STEPS_FLOW_UNAVAILABLE = "steps_flow_unavailable"
    STEPS_PARTICIPANT_NOT_FOUND = "steps_participant_not_found"
    STEPS_PARTICIPANT_NOT_ELIGIBLE = "steps_participant_not_eligible"
    STEPS_STAGE_CLOSED = "steps_stage_closed"
    STEPS_ACTIVE_GOAL_MISSING = "steps_active_goal_missing"
    FOCUS_PARTICIPANT_NOT_ELIGIBLE = "focus_participant_not_eligible"
    FOCUS_SELECTION_NOT_REQUESTED = "focus_selection_not_requested"


_DIAGNOSTICS: dict[ActionDiagnosticKind, tuple[str, str, str, str, str]] = {
    ActionDiagnosticKind.GOAL_FLOW_UNAVAILABLE: (
        "goal_setup", "flow_unavailable", "check_active_flow_binding",
        "Goal setup stage is not active", "бот не нашёл привязанный активный поток",
    ),
    ActionDiagnosticKind.GOAL_STAGE_CLOSED: (
        "goal_setup", "stage_closed", "check_flow_schedule_and_stage_dates",
        "Goal setup stage is not active", "участник пытался записать цель вне разрешённого этапа",
    ),
    ActionDiagnosticKind.GOAL_PARTICIPANT_NOT_FOUND: (
        "goal_setup", "participant_not_found", "check_participant_flow_and_telegram_id",
        "Goal participant is not available", "участник не найден в активном потоке",
    ),
    ActionDiagnosticKind.GOAL_CONSENT_MISSING: (
        "goal_setup", "consent_missing", "ask_participant_to_accept_personal_data_consent",
        "Goal participant consent is missing", "у участника нет согласия на обработку персональных данных",
    ),
    ActionDiagnosticKind.GOAL_PARTICIPANT_INACTIVE: (
        "goal_setup", "participant_inactive", "check_participant_status",
        "Goal participant is not active", "участник имеет неактивный статус",
    ),
    ActionDiagnosticKind.STEPS_FLOW_UNAVAILABLE: (
        "steps_setup", "flow_unavailable", "check_active_flow_binding",
        "Steps setup flow is unavailable", "бот не нашёл привязанный активный поток",
    ),
    ActionDiagnosticKind.STEPS_PARTICIPANT_NOT_FOUND: (
        "steps_setup", "participant_not_found", "check_participant_flow_and_telegram_id",
        "Steps participant is unavailable", "участник не найден в активном потоке",
    ),
    ActionDiagnosticKind.STEPS_PARTICIPANT_NOT_ELIGIBLE: (
        "steps_setup", "participant_not_eligible", "check_participant_status_role_consent_and_team",
        "Steps participant is not eligible", "участник не допущен к записи шагов",
    ),
    ActionDiagnosticKind.STEPS_STAGE_CLOSED: (
        "steps_setup", "stage_closed", "check_flow_schedule_and_stage_dates",
        "Steps setup stage is not active", "участник пытался записать шаги вне разрешённого этапа",
    ),
    ActionDiagnosticKind.STEPS_ACTIVE_GOAL_MISSING: (
        "steps_setup", "active_goal_missing", "ask_participant_to_save_goal_first",
        "Active goal is required", "для записи шагов не найдена активная цель",
    ),
    ActionDiagnosticKind.FOCUS_PARTICIPANT_NOT_ELIGIBLE: (
        "weekly_focus", "participant_not_eligible", "check_participant_status_role_consent_and_team",
        "Weekly focus participant is not eligible", "участник не допущен к выбору фокуса недели",
    ),
    ActionDiagnosticKind.FOCUS_SELECTION_NOT_REQUESTED: (
        "weekly_focus", "selection_not_requested", "ask_participant_to_open_weekly_focus_from_menu",
        "Weekly focus selection was not requested", "нажата устаревшая или неподходящая кнопка выбора фокуса",
    ),
}


_OPERATOR_CHECKS: dict[tuple[str, str], str] = {
    ("goal_setup", "flow_unavailable"): "проверьте привязку таблицы потока",
    ("goal_setup", "stage_closed"): "проверьте даты постановки цели и поздней регистрации",
    ("goal_setup", "participant_not_found"): "проверьте Telegram ID и flow_id участника",
    ("goal_setup", "consent_missing"): "участнику нужно пройти согласие через /start",
    ("goal_setup", "participant_inactive"): "проверьте status участника",
    ("steps_setup", "flow_unavailable"): "проверьте привязку таблицы потока",
    ("steps_setup", "participant_not_found"): "проверьте Telegram ID и flow_id участника",
    ("steps_setup", "participant_not_eligible"): "проверьте роль, статус, согласие и активность команды",
    ("steps_setup", "stage_closed"): "проверьте даты формирования шагов и поздней регистрации",
    ("steps_setup", "active_goal_missing"): "сначала сохраните цель участника",
    ("weekly_focus", "participant_not_eligible"): "проверьте роль, статус, согласие и активность команды",
    ("weekly_focus", "selection_not_requested"): "участнику нужно заново открыть выбор фокуса из меню",
}


class ActionDiagnosticError(PermissionError):
    """Expected action denial selected from a closed, non-PII diagnostic catalog."""

    def __init__(self, kind: ActionDiagnosticKind) -> None:
        action, reason, hint, legacy_message, _cause = _DIAGNOSTICS[kind]
        super().__init__(legacy_message)
        self.kind = kind
        self.action = action
        self.reason = reason
        self.hint = hint


def action_diagnostic_explanation(error: ActionDiagnosticError) -> str:
    """Return a fixed Russian explanation without interpolating business data."""

    action, reason, _hint, _legacy_message, cause = _DIAGNOSTICS[error.kind]
    check = _OPERATOR_CHECKS[(action, reason)]
    return f"Причина: {cause}. Что проверить: {check}."
