from app.services.weekly_report_models import WeeklyReportStatus

from tests.test_weekly_report_start_flow import NOW, _service, _user


def test_step_report_asks_metric_status_and_saves_actual_result(tmp_path) -> None:
    service, gateway, drafts, main_bot, _error_bot = _service(tmp_path)
    gateway._planned_steps[0]["step_description"] = "Провести встречи"
    gateway._planned_steps[0]["step_metric"] = "Не менее 10 встреч"

    started = service.start_report_for_step(_user(), step_id="S001", now=NOW)
    assert started.text == (
        "Шаг 1. Первый шаг\n\n"
        "Суть: Провести встречи\n\n"
        "Метрика: Не менее 10 встреч\n\n"
        "Как выполнена метрика этого шага?"
    )
    assert [button.callback_data for button in started.buttons] == [
        "weekly:metric:completed",
        "weekly:metric:partial",
        "weekly:metric:not_completed",
    ]

    prompt = service.select_metric_result(_user(), "partial", now=NOW)
    assert prompt.text == (
        "Укажи фактический результат по метрике. Например: «Провёл 8 из 10 встреч»."
    )
    service.add_text_message(_user(), "Провёл 8 из 10 встреч", now=NOW)
    saved = service.finalize_report(_user(), now=NOW)

    assert saved.text == "Принято. Частичная победа сохранена."
    report = gateway.list_weekly_reports()[0]
    relation = gateway.list_weekly_report_steps()[0]
    assert report["status_code"] == WeeklyReportStatus.BLUE.code
    assert relation["relation_status"] == "partial"
    assert relation["metric_status"] == "partial"
    assert relation["metric_result_text"] == "Провёл 8 из 10 встреч"
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "partial"
    assert drafts.get_active_draft(1001) is None
    assert main_bot.sent_messages[-1].text == saved.text


def test_not_completed_metric_keeps_step_open_but_saves_relation(tmp_path) -> None:
    service, gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)
    service.start_report_for_step(_user(), step_id="S001", now=NOW)
    service.select_metric_result(_user(), "not_completed", now=NOW)
    service.add_text_message(_user(), "Сделал 0 из 10", now=NOW)
    service.finalize_report(_user(), now=NOW)

    relation = gateway.list_weekly_report_steps()[0]
    assert gateway.list_weekly_reports()[0]["status_code"] == "red"
    assert relation["relation_status"] == "mentioned"
    assert relation["metric_status"] == "not_completed"
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "open"


def test_completed_metric_closes_only_selected_step_with_final_facts(tmp_path) -> None:
    service, gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)
    service.start_report_for_step(_user(), step_id="S001", now=NOW)
    service.select_metric_result(_user(), "completed", now=NOW)
    service.add_text_message(_user(), "Провёл 10 из 10 встреч", now=NOW)

    service.finalize_report(_user(), now=NOW)

    report = gateway.list_weekly_reports()[0]
    relation = gateway.list_weekly_report_steps()[0]
    steps = {row["step_id"]: row for row in gateway.list_planned_steps("P001", "G001")}
    assert report["status_code"] == "green"
    assert relation["relation_status"] == "closed"
    assert relation["metric_status"] == "completed"
    assert relation["metric_result_text"] == "Провёл 10 из 10 встреч"
    assert steps["S001"]["closed_week_number"] == 4
    assert steps["S001"]["closed_report_id"] == report["weekly_report_id"]
    assert steps["S001"]["closed_at"] == NOW.isoformat()
    assert steps["S002"]["step_status"] == "open"


def test_same_step_can_be_reported_again_in_a_later_week(tmp_path) -> None:
    old_report = {
        "weekly_report_id": "WR:P001:week-03:step-S001",
        "participant_id": "P001", "week_number": 3,
    }
    old_relation = {
        "weekly_report_step_id": "WRS:old:S001",
        "weekly_report_id": old_report["weekly_report_id"],
        "participant_id": "P001", "step_id": "S001",
    }
    service, gateway, _drafts, _main_bot, _error_bot = _service(
        tmp_path, weekly_reports=[old_report], weekly_report_steps=[old_relation]
    )
    service.start_report_for_step(_user(), step_id="S001", now=NOW)
    service.select_metric_result(_user(), "partial", now=NOW)
    service.add_text_message(_user(), "Продвинулся на 50%", now=NOW)

    service.finalize_report(_user(), now=NOW)

    assert sorted(row["week_number"] for row in gateway.list_weekly_reports()) == [3, 4]
    assert len(gateway.list_weekly_report_steps()) == 2


def test_completed_metric_retry_reconciles_parent_step_and_relation(tmp_path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    service.start_report_for_step(_user(), step_id="S001", now=NOW)
    service.select_metric_result(_user(), "completed", now=NOW)
    service.add_text_message(_user(), "10 из 10", now=NOW)
    original = gateway.close_planned_steps
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("step write failed")
        return original(*args, **kwargs)

    gateway.close_planned_steps = fail_once  # type: ignore[method-assign]
    import pytest
    with pytest.raises(RuntimeError, match="step write failed"):
        service.finalize_report(_user(), now=NOW)
    assert drafts.get_active_draft(1001) is not None

    service.finalize_report(_user(), now=NOW)

    assert len(gateway.list_weekly_reports()) == 1
    assert len(gateway.list_weekly_report_steps()) == 1
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "closed"
    assert drafts.get_active_draft(1001) is None


def test_ambiguous_relation_write_is_reconciled_without_duplicate(tmp_path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    service.start_report_for_step(_user(), step_id="S001", now=NOW)
    service.select_metric_result(_user(), "partial", now=NOW)
    service.add_text_message(_user(), "5 из 10", now=NOW)
    original = gateway.append_weekly_report_step
    calls = 0

    def persist_then_fail(row):
        nonlocal calls
        calls += 1
        original(row)
        if calls == 1:
            raise RuntimeError("ambiguous relation response")

    gateway.append_weekly_report_step = persist_then_fail  # type: ignore[method-assign]
    import pytest
    with pytest.raises(RuntimeError, match="ambiguous relation response"):
        service.finalize_report(_user(), now=NOW)
    assert drafts.get_active_draft(1001) is not None

    service.finalize_report(_user(), now=NOW)

    assert len(gateway.list_weekly_reports()) == 1
    assert len(gateway.list_weekly_report_steps()) == 1
    assert drafts.get_active_draft(1001) is None
