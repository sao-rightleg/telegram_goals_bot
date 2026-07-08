from app.bot.messages import (
    format_scheduler_reminder_text,
    format_silent_participants_notification,
)
from app.scheduler.jobs import ReminderJobResult, SilentParticipant, WeekCloseResult


def test_scheduler_reminder_texts_are_approved_russian_copy() -> None:
    assert format_scheduler_reminder_text("monday_reminder") == (
        "Новая неделя началась.\n\n"
        "Проверь свои шаги и запланируй победу недели."
    )
    assert format_scheduler_reminder_text("wednesday_checkin") == (
        "Короткий чек-ап.\n\n"
        "Как идёт движение по шагам на этой неделе?"
    )
    assert format_scheduler_reminder_text("sunday_1800_checkin") == (
        "Дедлайн отчёта сегодня в 23:59 по Екатеринбургу."
    )
    assert format_scheduler_reminder_text("sunday_2230_reminder") == (
        "Напоминание: отчёт за неделю ещё не отправлен.\n\n"
        "Дедлайн сегодня в 23:59 по Екатеринбургу."
    )
    assert format_scheduler_reminder_text("sunday_2300_reminder") == (
        "Последнее напоминание.\n\n"
        "Если отчёт не будет отправлен до 23:59 по Екатеринбургу, "
        "неделя будет отмечена как ⬜ нет ответа."
    )

    sunday_1800 = format_scheduler_reminder_text("sunday_1800_checkin")
    assert "🟩" not in sunday_1800
    assert "🟦" not in sunday_1800
    assert "🟥" not in sunday_1800
    assert "Выбери статус" not in sunday_1800


def test_silent_participant_notification_lists_names_only() -> None:
    participants = (
        SilentParticipant(participant_id="P001", team_id="T001", full_name="Иван Иванов"),
        SilentParticipant(participant_id="P002", team_id="T001", full_name="Участник без имени"),
    )

    text = format_silent_participants_notification(week_number=4, participants=participants)

    assert text == (
        "Нет отчёта за неделю 4: 2 участник(ов).\n"
        "- Иван Иванов\n"
        "- Участник без имени"
    )
    assert "P001" not in text
    assert "T001" not in text
    assert "черновик" not in text.lower()
    assert "draft" not in text.lower()


def test_scheduler_result_contracts_expose_counts() -> None:
    reminder = ReminderJobResult(sent_count=5, skipped_count=2, failed_count=1)
    week_close = WeekCloseResult(
        gray_created_count=3,
        existing_count=4,
        failed_count=1,
        notified_team_count=2,
    )

    assert reminder.sent_count == 5
    assert reminder.skipped_count == 2
    assert reminder.failed_count == 1
    assert week_close.gray_created_count == 3
    assert week_close.existing_count == 4
    assert week_close.failed_count == 1
    assert week_close.notified_team_count == 2
