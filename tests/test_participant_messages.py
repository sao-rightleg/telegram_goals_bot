from app.bot.menus import (
    CAPTAIN_MENU_LABELS,
    PARTICIPANT_MENU_LABELS,
    MenuAction,
    build_role_menu,
)
from app.bot.messages import (
    CAPTAIN_DROPPED_PARTICIPANT_TEXT,
    CAPTAIN_EMPTY_REPORT_TEXT,
    CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT,
    CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT,
    CAPTAIN_MANUAL_REPORT_LATE_TEXT,
    CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT,
    CAPTAIN_NO_TEAM_MEMBERS_TEXT,
    CAPTAIN_TEAM_TITLE_TEXT,
    CONSENT_ACCEPT_BUTTON,
    CONSENT_TEXT,
    UNKNOWN_USER_TEXT,
    format_captain_team_member_line,
    format_goal_view,
    format_missing_data_message,
    format_planned_steps_view,
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
        MenuAction.START_WEEKLY_REPORT,
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


def test_steps_formatter_renders_focus_and_spoiler_description_after_15_chars() -> None:
    steps = [
        PlannedStep(
            step_id="S001",
            participant_id="P001",
            goal_id="G001",
            step_number=2,
            step_title="Созвон с клиентом",
            step_description="Подробно описать следующий шаг и критерий готовности",
            step_status="open",
        )
    ]

    text = format_planned_steps_view(steps, focus_step_id="S001")

    assert "⬜ Шаг 2. 🎯 Созвон с клиентом" in text
    assert "Подробно описат<tg-spoiler>ь следующий шаг и критерий готовности</tg-spoiler>" in text
    assert "<blockquote expandable>" not in text


def test_missing_data_message_hides_internal_fields() -> None:
    text = format_missing_data_message()

    assert text == "Данные пока не заполнены. Свяжитесь со своим капитаном."
    assert "team_id" not in text
    assert "goal_id" not in text
    assert "token" not in text.lower()


def test_captain_manual_report_messages_are_safe() -> None:
    texts = (
        CAPTAIN_TEAM_TITLE_TEXT,
        CAPTAIN_NO_TEAM_MEMBERS_TEXT,
        CAPTAIN_FORBIDDEN_PARTICIPANT_TEXT,
        CAPTAIN_DROPPED_PARTICIPANT_TEXT,
        CAPTAIN_MANUAL_REPORT_DUPLICATE_TEXT,
        CAPTAIN_MANUAL_REPORT_LATE_TEXT,
        CAPTAIN_EMPTY_REPORT_TEXT,
        CAPTAIN_MANUAL_REPORT_SUCCESS_TEXT,
        format_captain_team_member_line(
            {
                "participant_id": "P001",
                "full_name": "Анна Иванова",
                "team_id": "T001",
                "telegram_id": 1001,
            }
        ),
    )

    joined = "\n".join(texts)
    assert "Анна Иванова" in joined
    assert "капитан" in joined.lower()
    for forbidden_fragment in ("P001", "T001", "team_id", "participant_id", "telegram_id", "token", "callback"):
        assert forbidden_fragment not in joined
