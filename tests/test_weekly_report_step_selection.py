from pathlib import Path

import pytest

from app.services.weekly_report_models import WeeklyReportStatus
from app.storage.sqlite import initialize_schema
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository

from tests.test_weekly_report_start_flow import NOW, _service, _step, _user


def test_green_requires_open_owned_steps(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)

    no_steps_response = service.select_steps(user, [], now=NOW)
    assert no_steps_response.text == "Выбери один или несколько открытых шагов."

    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)
    response = service.select_steps(user, ["S001"], now=NOW)

    draft = drafts.get_active_draft(1001)
    assert response.text == "Что именно ты сделал?"
    assert draft is not None
    assert draft.status_code == "green"
    assert draft.selected_step_ids == ("S001",)

    closed_response = service.select_steps(user, ["S003"], now=NOW)
    assert closed_response.text == "Выбери один или несколько открытых шагов."
    assert drafts.get_active_draft(1001).selected_step_ids == ("S001",)


def test_blue_requires_owned_steps_without_closing_them(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.BLUE, now=NOW)

    response = service.select_steps(user, ["S001", "S002"], now=NOW)

    draft = drafts.get_active_draft(1001)
    assert response.text == "Что получилось сделать частично?"
    assert draft is not None
    assert draft.status_code == "blue"
    assert draft.selected_step_ids == ("S001", "S002")
    assert [row["step_status"] for row in gateway.list_planned_steps("P001", "G001")] == [
        "open",
        "open",
        "closed",
    ]


def test_red_does_not_require_selected_steps(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)

    response = service.select_status(user, WeeklyReportStatus.RED, now=NOW)

    draft = drafts.get_active_draft(1001)
    assert response.text == "Что помешало сделать победу недели?"
    assert draft is not None
    assert draft.status_code == "red"
    assert draft.selected_step_ids == ()


def test_cross_participant_step_selection_is_rejected(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(
        tmp_path,
        planned_steps=[
            _step("S001", 1, "Первый шаг", "open"),
            {
                "step_id": "S999",
                "participant_id": "P002",
                "goal_id": "G001",
                "step_number": 2,
                "step_title": "Чужой шаг",
                "step_status": "open",
            },
        ],
    )
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)

    response = service.select_steps(user, ["S999"], now=NOW)

    assert response.text == "Выбери один или несколько открытых шагов."
    assert drafts.get_active_draft(1001).selected_step_ids == ()


def test_select_status_allows_progress_when_another_step_report_exists_same_week(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4})

    response = service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)

    assert response.text == "Выбери один или несколько открытых шагов."
    assert drafts.get_active_draft(1001).status_code == "green"


def test_select_steps_requires_active_draft(tmp_path: Path) -> None:
    service, _gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)

    with pytest.raises(KeyError):
        service.select_steps(_user(), ["S001"], now=NOW)
