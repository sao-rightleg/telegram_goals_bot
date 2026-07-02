from app.bot.menus import (
    CAPTAIN_MENU_LABELS,
    PARTICIPANT_MENU_LABELS,
    MenuAction,
    build_role_menu,
)
from app.bot.messages import (
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    UNKNOWN_USER_TEXT,
    format_goal_view,
    format_missing_data_message,
    format_progress_view,
)
from app.services.participant_models import Goal, PlannedStep, WeeklyStatus


def test_unknown_user_message_matches_approved_copy() -> None:
    assert UNKNOWN_USER_TEXT == "Извините, вас нет в базе участников. Свяжитесь со своим капитаном."


def test_consent_message_matches_approved_copy() -> None:
    assert (
        CONSENT_TEXT
        == "Я понимаю, что мои ответы будут сохранены и доступны трекеру, администратору и Александру Ситникову в рамках челленджа."
    )
    assert CONSENT_ACCEPT_BUTTON == "✅ Согласен"


def test_participant_menu_contains_approved_buttons_only() -> None:
    menu = build_role_menu("participant")

    assert [item.label for item in menu] == PARTICIPANT_MENU_LABELS
    assert [item.action for item in menu] == [
        MenuAction.VIEW_GOAL,
        MenuAction.VIEW_STEPS,
        MenuAction.VIEW_PROGRESS,
        MenuAction.VIEW_INSIGHTS,
    ]


def test_captain_menu_extends_participant_menu() -> None:
    menu = build_role_menu("captain")

    assert [item.label for item in menu] == CAPTAIN_MENU_LABELS
    assert CAPTAIN_MENU_LABELS[: len(PARTICIPANT_MENU_LABELS)] == PARTICIPANT_MENU_LABELS
    assert [item.action for item in menu][-3:] == [
        MenuAction.VIEW_TEAM,
        MenuAction.CAPTAIN_MANUAL_REPORT,
        MenuAction.VIEW_TEAM_REPORT,
    ]


def test_unknown_role_gets_participant_menu_without_captain_actions() -> None:
    menu = build_role_menu("tracker")

    assert [item.label for item in menu] == PARTICIPANT_MENU_LABELS
    assert MenuAction.VIEW_TEAM not in [item.action for item in menu]


def test_goal_formatter_renders_goal_fields() -> None:
    goal = Goal(
        goal_id="G001",
        participant_id="P001",
        goal_title="Новый контракт",
        goal_description="Заключить контракт с клиентом",
        goal_value_amount="100000",
        goal_value_currency="RUB",
        permission_condition="Оплата получена",
        goal_status="active",
    )

    text = format_goal_view(goal)

    assert "Новый контракт" in text
    assert "Заключить контракт с клиентом" in text
    assert "100000 RUB" in text
    assert "Оплата получена" in text


def test_progress_formatter_uses_six_cells_and_percent() -> None:
    steps = [
        PlannedStep(
            step_id=f"S00{index}",
            participant_id="P001",
            goal_id="G001",
            step_number=index,
            step_title=f"Шаг {index}",
            step_description="",
            step_status="closed" if index <= 3 else "open",
        )
        for index in range(1, 7)
    ]
    history = [WeeklyStatus(week_number=1, status_symbol="🟩", status_code="green")]

    text = format_progress_view(steps=steps, weekly_history=history)

    assert "50%" in text
    assert text.count("■") == 3
    assert text.count("□") == 3
    assert "🟩" in text


def test_missing_data_message_hides_internal_fields() -> None:
    text = format_missing_data_message()

    assert text == "Данные пока не заполнены. Свяжитесь со своим капитаном."
    assert "team_id" not in text
    assert "goal_id" not in text
    assert "token" not in text.lower()
