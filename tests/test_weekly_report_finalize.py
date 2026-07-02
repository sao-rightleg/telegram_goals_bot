from pathlib import Path

from app.bot.messages import WEEKLY_REPORT_EMPTY_TEXT, WEEKLY_REPORT_LATE_TEXT, WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT
from app.services.weekly_report_models import WeeklyReportStatus

from tests.test_weekly_report_start_flow import LATE, NOW, _service, _user


def test_green_report_saves_weekly_report_relations_closes_steps_and_clears_draft(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Сделал первый шаг", now=NOW)

    response = service.finalize_report(user, now=NOW)

    assert response.text == "Принято. Победа недели сохранена."
    assert drafts.get_active_draft(1001) is None
    assert gateway.list_weekly_reports() == [
        {
            "weekly_report_id": "WR:P001:week-04",
            "participant_id": "P001",
            "team_id": "T001",
            "goal_id": "G001",
            "week_number": 4,
            "status_code": "green",
            "status_symbol": "🟩",
            "score": 1,
            "report_text": "Сделал первый шаг",
            "submitted_at": NOW.isoformat(),
            "submitted_by_id": "P001",
            "submitted_by_role": "participant",
            "flow_source": "participant_bot",
        }
    ]
    assert gateway.list_weekly_report_steps() == [
        {
            "weekly_report_step_id": "WRS:WR:P001:week-04:S001",
            "weekly_report_id": "WR:P001:week-04",
            "participant_id": "P001",
            "goal_id": "G001",
            "step_id": "S001",
            "week_number": 4,
            "relation_status": "closed",
            "created_at": NOW.isoformat(),
        }
    ]
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "closed"


def test_blue_report_saves_partial_relations_without_closing_steps(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.BLUE, now=NOW)
    service.select_steps(user, ["S001", "S002"], now=NOW)
    service.add_text_message(user, "Сделал часть", now=NOW)

    response = service.finalize_report(user, now=NOW)

    assert response.text == "Принято. Частичная победа сохранена."
    assert drafts.get_active_draft(1001) is None
    assert gateway.list_weekly_reports()[0]["status_code"] == "blue"
    assert gateway.list_weekly_reports()[0]["status_symbol"] == "🟦"
    assert gateway.list_weekly_reports()[0]["score"] == 0.5
    assert [row["relation_status"] for row in gateway.list_weekly_report_steps()] == ["partial", "partial"]
    assert [row["step_status"] for row in gateway.list_planned_steps("P001", "G001")] == [
        "open",
        "open",
        "closed",
    ]


def test_red_report_saves_without_selected_steps_or_relations(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.RED, now=NOW)
    service.add_text_message(user, "Не успел", now=NOW)

    response = service.finalize_report(user, now=NOW)

    assert response.text == "Принято. Отчёт за неделю сохранён."
    assert drafts.get_active_draft(1001) is None
    assert gateway.list_weekly_reports()[0]["status_code"] == "red"
    assert gateway.list_weekly_reports()[0]["status_symbol"] == "🟥"
    assert gateway.list_weekly_reports()[0]["score"] == 0
    assert gateway.list_weekly_report_steps() == []
    assert [row["step_status"] for row in gateway.list_planned_steps("P001", "G001")] == [
        "open",
        "open",
        "closed",
    ]


def test_finalize_without_text_does_not_create_weekly_report(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)

    response = service.finalize_report(user, now=NOW)

    assert response.text == WEEKLY_REPORT_EMPTY_TEXT
    assert gateway.list_weekly_reports() == []
    assert drafts.get_active_draft(1001) is not None


def test_ordered_text_messages_are_joined_in_message_order(tmp_path: Path) -> None:
    service, gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)

    service.add_text_message(user, "Первое", now=NOW, telegram_message_id=501)
    service.add_text_message(user, "Второе", now=NOW, telegram_message_id=502)
    service.finalize_report(user, now=NOW)

    assert gateway.list_weekly_reports()[0]["report_text"] == "Первое\nВторое"


def test_finalize_rejects_late_report_without_final_facts(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Сделал", now=NOW)

    response = service.finalize_report(user, now=LATE)

    assert response.text == WEEKLY_REPORT_LATE_TEXT
    assert gateway.list_weekly_reports() == []
    assert drafts.get_active_draft(1001) is not None


def test_finalize_rejects_duplicate_report_without_final_facts(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Сделал", now=NOW)
    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4})

    response = service.finalize_report(user, now=NOW)

    assert response.text == "Отчёт за эту неделю уже принят."
    assert len(gateway.list_weekly_reports()) == 1
    assert drafts.get_active_draft(1001) is not None


def test_voice_message_returns_not_available_without_attachment_state(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)

    response = service.reject_voice_message(user, now=NOW)

    assert response.text == WEEKLY_REPORT_VOICE_NOT_AVAILABLE_TEXT
    assert drafts.get_active_draft(1001).message_count == 0


def test_goal_is_not_auto_achieved_when_all_steps_close(tmp_path: Path) -> None:
    service, gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)
    service.select_steps(user, ["S001", "S002"], now=NOW)
    service.add_text_message(user, "Закрыл два шага", now=NOW)

    service.finalize_report(user, now=NOW)

    assert gateway.get_active_goal("P001")["goal_status"] == "active"


def _prepare_green(service, user) -> None:
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)
    service.select_steps(user, ["S001"], now=NOW)
