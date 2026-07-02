from app.bot.messages import (
    WEEKLY_REPORT_BLUE_SUCCESS_TEXT,
    WEEKLY_REPORT_EMPTY_TEXT,
    WEEKLY_REPORT_GREEN_SUCCESS_TEXT,
    WEEKLY_REPORT_LATE_TEXT,
    WEEKLY_REPORT_RED_SUCCESS_TEXT,
    WEEKLY_REPORT_RECOVERY_TEXT,
    WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT,
    build_weekly_report_status_buttons,
    format_weekly_report_status_prompt,
    get_weekly_report_success_text,
)
from app.services.weekly_report_models import WeeklyReportStatus


def test_weekly_report_status_mapping_matches_spec() -> None:
    assert WeeklyReportStatus.GREEN.code == "green"
    assert WeeklyReportStatus.GREEN.symbol == "🟩"
    assert WeeklyReportStatus.GREEN.score == 1

    assert WeeklyReportStatus.BLUE.code == "blue"
    assert WeeklyReportStatus.BLUE.symbol == "🟦"
    assert WeeklyReportStatus.BLUE.score == 0.5

    assert WeeklyReportStatus.RED.code == "red"
    assert WeeklyReportStatus.RED.symbol == "🟥"
    assert WeeklyReportStatus.RED.score == 0


def test_weekly_report_status_buttons_match_user_spec() -> None:
    assert build_weekly_report_status_buttons() == (
        "🟩 Победа есть",
        "🟦 Частично",
        "🟥 Победы нет",
    )


def test_weekly_report_success_messages_match_spec() -> None:
    assert WEEKLY_REPORT_GREEN_SUCCESS_TEXT == "Принято. Победа недели сохранена."
    assert WEEKLY_REPORT_BLUE_SUCCESS_TEXT == "Принято. Частичная победа сохранена."
    assert WEEKLY_REPORT_RED_SUCCESS_TEXT == "Принято. Отчёт за неделю сохранён."

    assert get_weekly_report_success_text(WeeklyReportStatus.GREEN) == WEEKLY_REPORT_GREEN_SUCCESS_TEXT
    assert get_weekly_report_success_text(WeeklyReportStatus.BLUE) == WEEKLY_REPORT_BLUE_SUCCESS_TEXT
    assert get_weekly_report_success_text(WeeklyReportStatus.RED) == WEEKLY_REPORT_RED_SUCCESS_TEXT


def test_weekly_report_validation_messages_are_short_and_safe() -> None:
    messages = [
        WEEKLY_REPORT_EMPTY_TEXT,
        WEEKLY_REPORT_LATE_TEXT,
        WEEKLY_REPORT_RECOVERY_TEXT,
        format_weekly_report_status_prompt(),
    ]

    for text in messages:
        assert len(text) <= 180
        assert "token" not in text.lower()
        assert "secret" not in text.lower()
        assert "participant_id" not in text
        assert "goal_id" not in text
        assert "draft_" not in text

    assert WEEKLY_REPORT_LATE_TEXT == "Дедлайн недели уже прошёл. Отчёт не может изменить статус."
    assert WEEKLY_REPORT_EMPTY_TEXT == "Отправь текст отчёта, потом нажми «✅ Готово»."


def test_voice_not_available_message_does_not_create_voice_state_contract() -> None:
    assert WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT == "Голосовые отчёты будут доступны позже. Сейчас отправь текст."
    assert "аудио" not in WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT.lower()
    assert "транскрип" not in WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT.lower()
