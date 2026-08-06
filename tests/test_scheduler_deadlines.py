from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.bot.clients import BotPurpose, FakeBotClient, OutgoingMessage
from app.bot.menus import WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX
from app.scheduler.calendar import TIMEZONE_NAME
from app.scheduler.jobs import SchedulerService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import FakeSheetsGateway
from app.storage.scheduler import SchedulerJobRepository
from app.storage.sqlite import initialize_schema
from app.storage.weekly_report_drafts import WeeklyReportDraftRepository


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))
MONDAY_START = datetime(2026, 6, 8, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))


def test_reminder_sends_only_to_active_consenting_participants_without_report(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=True),
        ],
    )

    result = service.run_reminder("wednesday_checkin", now=NOW)

    assert result.sent_count == 2
    assert result.skipped_count == 0
    assert result.failed_count == 0
    assert [message.chat_id for message in main_bot.sent_messages] == ["1001", "1002"]
    assert all("Короткий чек-ап" in message.text for message in main_bot.sent_messages)


def test_monday_reminder_prompts_weekly_focus_when_open_steps_exist(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
        goals=[_goal("G001", "P001")],
        planned_steps=[
            _step("S002", "P001", "G001", 2, "Второй шаг", "open"),
            _step("S001", "P001", "G001", 1, "Первый шаг", "open"),
            _step("S003", "P001", "G001", 3, "Закрытый шаг", "closed"),
        ],
    )

    result = service.run_reminder("monday_reminder", now=MONDAY_START)

    assert result.sent_count == 1
    assert "Выбери обязательный фокус недели." in main_bot.sent_messages[0].text
    assert [button.text for button in main_bot.sent_messages[0].buttons] == [
        "Шаг 1. Первый шаг",
        "Шаг 2. Второй шаг",
    ]
    assert [button.callback_data for button in main_bot.sent_messages[0].buttons] == [
        f"{WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX}S001",
        f"{WEEKLY_FOCUS_SELECT_CALLBACK_PREFIX}S002",
    ]


def test_monday_reminder_falls_back_to_plain_text_when_focus_already_selected(
    tmp_path: Path,
) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
        goals=[_goal("G001", "P001")],
        planned_steps=[_step("S001", "P001", "G001", 1, "Первый шаг", "open")],
        weekly_focus=[
            {
                "focus_id": "WF:P001:week-01",
                "participant_id": "P001",
                "goal_id": "G001",
                "step_id": "S001",
                "week_number": 1,
                "focus_status": "active",
            }
        ],
    )

    service.run_reminder("monday_reminder", now=MONDAY_START)

    assert "Новая неделя началась." in main_bot.sent_messages[0].text
    assert main_bot.sent_messages[0].buttons == ()


def test_reminder_skips_dropped_non_consenting_and_already_reported_participants(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=False),
            _participant("P003", 1003, consent=True, status="dropped"),
            _participant("P004", 1004, consent=True),
        ],
        weekly_reports=[
            {"weekly_report_id": "WR:P004:week-04", "participant_id": "P004", "week_number": 4}
        ],
    )

    result = service.run_reminder("wednesday_checkin", now=NOW)

    assert result.sent_count == 1
    assert result.skipped_count == 3
    assert result.failed_count == 0
    assert [message.chat_id for message in main_bot.sent_messages] == ["1001"]


def test_sunday_1800_reminder_does_not_start_report_flow(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
    )

    service.run_reminder("sunday_1800_checkin", now=NOW)

    assert main_bot.sent_messages[0].text == "Дедлайн отчёта сегодня в 23:59 по Екатеринбургу."
    assert "🟩" not in main_bot.sent_messages[0].text
    assert "Выбери статус" not in main_bot.sent_messages[0].text


def test_failed_participant_send_retries_three_times_without_blocking_others(tmp_path: Path) -> None:
    service, _gateway, main_bot, error_bot = _service(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=True),
        ],
        failing_chat_ids={"1001"},
    )

    result = service.run_reminder("sunday_2300_reminder", now=NOW)

    assert result.sent_count == 1
    assert result.skipped_count == 0
    assert result.failed_count == 1
    assert main_bot.attempts_by_chat_id["1001"] == 3
    assert main_bot.attempts_by_chat_id["1002"] == 1
    assert [message.chat_id for message in main_bot.sent_messages] == ["1002"]
    assert "reminder_send_failed" in error_bot.sent_messages[-1].text
    assert "P001" in error_bot.sent_messages[-1].text


def test_failed_reminder_after_retry_exhaustion_notifies_admin(tmp_path: Path) -> None:
    service, _gateway, _main_bot, error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
        failing_chat_ids={"1001"},
    )

    result = service.run_reminder("sunday_2300_reminder", now=NOW)

    assert result.failed_count == 1
    assert len(error_bot.sent_messages) == 1
    assert error_bot.sent_messages[0].chat_id == "admin-errors"
    assert "reminder_send_failed" in error_bot.sent_messages[0].text


def test_reminder_rerun_skips_participants_already_successfully_sent(tmp_path: Path) -> None:
    service, _gateway, main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
    )

    first = service.run_reminder("wednesday_checkin", now=NOW)
    second = service.run_reminder("wednesday_checkin", now=NOW)

    assert first.sent_count == 1
    assert second.sent_count == 0
    assert second.skipped_count == 1
    assert [message.chat_id for message in main_bot.sent_messages] == ["1001"]


def test_admin_error_omits_raw_adapter_exception_details(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    service, _gateway, _main_bot, error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
        failing_chat_ids={"1001"},
        failure_message="telegram failed token=SECRET https://api.telegram.org/botSECRET/sendMessage chat_id=1001",
    )

    service.run_reminder("sunday_2300_reminder", now=NOW)

    assert error_bot.sent_messages[0].text == "reminder_send_failed participant_id=P001"
    with sqlite3.connect(db_path) as connection:
        messages = [
            row[0]
            for row in connection.execute(
                "SELECT message FROM error_events WHERE error_type = 'reminder_send_failed'"
            ).fetchall()
        ]

    assert messages == ["reminder_send_failed participant_id=P001"]
    assert all("SECRET" not in message for message in messages)
    assert all("api.telegram.org" not in message for message in messages)
    assert all("chat_id=1001" not in message for message in messages)


def test_week_close_creates_gray_reports_for_active_missing_participants(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=True),
        ],
        goals=[
            {"goal_id": "G001", "participant_id": "P001", "goal_status": "active"},
            {"goal_id": "G002", "participant_id": "P002", "goal_status": "active"},
        ],
    )

    result = service.close_week(now=NOW)

    assert result.gray_created_count == 2
    assert result.existing_count == 0
    reports = gateway.list_weekly_reports()
    assert [row["participant_id"] for row in reports] == ["P001", "P002"]
    assert {row["status_code"] for row in reports} == {"gray"}
    assert {row["status_symbol"] for row in reports} == {"⬜"}
    assert {row["submitted_by_role"] for row in reports} == {"system"}
    assert {row["submitted_source"] for row in reports} == {"system_deadline"}
    assert {row["score"] for row in reports} == {0}
    assert {row["status_score"] for row in reports} == {0}


def test_week_close_includes_non_consenting_active_participants(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=False)],
    )

    result = service.close_week(now=NOW)

    assert result.gray_created_count == 1
    assert gateway.list_weekly_reports()[0]["participant_id"] == "P001"


def test_week_close_skips_dropped_and_already_reported_participants(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=True, status="dropped"),
            _participant("P003", 1003, consent=True),
        ],
        weekly_reports=[
            {"weekly_report_id": "WR:P003:week-04", "participant_id": "P003", "week_number": 4}
        ],
    )

    result = service.close_week(now=NOW)

    assert result.gray_created_count == 1
    assert result.existing_count == 1
    assert [row["participant_id"] for row in gateway.list_weekly_reports()] == ["P003", "P001"]


def test_week_close_is_idempotent_on_rerun(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
    )

    first = service.close_week(now=NOW)
    second = service.close_week(now=NOW)

    assert first.gray_created_count == 1
    assert second.gray_created_count == 0
    assert second.existing_count == 1
    assert len(gateway.list_weekly_reports()) == 1


def test_week_close_rerun_after_partial_failure_creates_only_missing_gray_rows(tmp_path: Path) -> None:
    gateway = FailsOnceAfterFirstGrayGateway(
        participants=[
            _participant("P001", 1001, consent=True),
            _participant("P002", 1002, consent=True),
        ]
    )
    service, _gateway, _main_bot, error_bot = _service(tmp_path, participants=[], gateway=gateway)

    first = service.close_week(now=NOW)
    second = service.close_week(now=NOW)

    assert first.gray_created_count == 1
    assert first.failed_count == 1
    assert second.gray_created_count == 1
    assert second.existing_count == 1
    assert [row["participant_id"] for row in gateway.list_weekly_reports()] == ["P001", "P002"]
    assert "week_close_gray_failed" in error_bot.sent_messages[0].text


def test_week_close_preserves_unfinished_drafts(tmp_path: Path) -> None:
    service, gateway, _main_bot, _error_bot = _service(
        tmp_path,
        participants=[_participant("P001", 1001, consent=True)],
    )
    drafts = WeeklyReportDraftRepository(tmp_path / "state.sqlite3")
    drafts.create_draft(
        draft_id="draft-P001-week-04",
        telegram_id=1001,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=4,
        occurred_at=NOW.isoformat(),
    )

    service.close_week(now=NOW)

    assert gateway.list_weekly_reports()[0]["participant_id"] == "P001"
    assert drafts.get_active_draft(1001) is not None


def test_week_close_sends_aggregated_silent_notification_to_captain_and_tracker(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, notification_bot = _service_with_notification_bot(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True, full_name="Иван Иванов"),
            _participant("C001", 2001, consent=True, role="captain", full_name="Капитан"),
        ],
        teams=[{"team_id": "T001", "captain_id": "C001", "tracker_id": "TR001"}],
        trackers=[{"tracker_id": "TR001", "telegram_id": 3001, "full_name": "Трекер"}],
    )

    result = service.close_week(now=NOW)

    assert result.notified_team_count == 1
    assert [message.chat_id for message in notification_bot.sent_messages] == ["2001", "3001"]
    assert notification_bot.sent_messages[0].text == (
        "Нет отчёта за неделю 4: 1 участник(ов).\n"
        "- Иван Иванов"
    )
    assert notification_bot.sent_messages[1].text == notification_bot.sent_messages[0].text


def test_silent_notifications_are_scoped_to_team(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, notification_bot = _service_with_notification_bot(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True, team_id="T001", full_name="Участник 1"),
            _participant("P002", 1002, consent=True, team_id="T002", full_name="Участник 2"),
            _participant("C001", 2001, consent=True, role="captain", team_id="T001"),
            _participant("C002", 2002, consent=True, role="captain", team_id="T002"),
        ],
        teams=[
            {"team_id": "T001", "captain_id": "C001", "tracker_id": "TR001"},
            {"team_id": "T002", "captain_id": "C002", "tracker_id": "TR002"},
        ],
        trackers=[
            {"tracker_id": "TR001", "telegram_id": 3001},
            {"tracker_id": "TR002", "telegram_id": 3002},
        ],
    )

    service.close_week(now=NOW)

    messages_by_chat = {message.chat_id: message.text for message in notification_bot.sent_messages}
    assert "Участник 1" in messages_by_chat["2001"]
    assert "Участник 2" not in messages_by_chat["2001"]
    assert "Участник 2" in messages_by_chat["2002"]
    assert "Участник 1" not in messages_by_chat["2002"]
    assert messages_by_chat["3001"] == messages_by_chat["2001"]
    assert messages_by_chat["3002"] == messages_by_chat["2002"]


def test_missing_captain_or_tracker_chat_id_notifies_admin_without_blocking_week_close(tmp_path: Path) -> None:
    service, gateway, _main_bot, error_bot, notification_bot = _service_with_notification_bot(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True, full_name="Иван Иванов"),
            {"participant_id": "C001", "team_id": "T001", "role": "captain", "status": "active"},
        ],
        teams=[{"team_id": "T001", "captain_id": "C001", "tracker_id": "TR001"}],
        trackers=[{"tracker_id": "TR001", "full_name": "Трекер"}],
    )

    result = service.close_week(now=NOW)

    assert result.gray_created_count == 2
    assert len(gateway.list_weekly_reports()) == 2
    assert notification_bot.sent_messages == []
    assert len(error_bot.sent_messages) == 2
    assert "silent_notification_missing_recipient" in error_bot.sent_messages[0].text


def test_silent_notification_does_not_include_draft_state(tmp_path: Path) -> None:
    service, _gateway, _main_bot, _error_bot, notification_bot = _service_with_notification_bot(
        tmp_path,
        participants=[
            _participant("P001", 1001, consent=True, full_name="Иван Иванов"),
            _participant("C001", 2001, consent=True, role="captain", full_name="Капитан"),
        ],
        teams=[{"team_id": "T001", "captain_id": "C001"}],
        trackers=[],
    )
    drafts = WeeklyReportDraftRepository(tmp_path / "state.sqlite3")
    drafts.create_draft(
        draft_id="draft-P001-week-04",
        telegram_id=1001,
        participant_id="P001",
        team_id="T001",
        goal_id="G001",
        week_number=4,
        occurred_at=NOW.isoformat(),
    )

    service.close_week(now=NOW)

    assert "Иван Иванов" in notification_bot.sent_messages[0].text
    assert "черновик" not in notification_bot.sent_messages[0].text.lower()
    assert "draft" not in notification_bot.sent_messages[0].text.lower()


def test_scheduler_acceptance_criteria_coverage() -> None:
    covered_by = {
        "approved schedule in Asia/Yekaterinburg": [
            "tests/test_scheduler_foundation.py::test_timezone_is_yekaterinburg",
            "tests/test_scheduler_foundation.py::test_reminder_schedule_matches_product_decisions",
        ],
        "reminders go only to active consenting participants without reports": [
            "test_reminder_sends_only_to_active_consenting_participants_without_report",
            "test_reminder_skips_dropped_non_consenting_and_already_reported_participants",
        ],
        "sunday 18:00 is text-only reminder": [
            "test_sunday_1800_reminder_does_not_start_report_flow",
        ],
        "participant send failure is isolated": [
            "test_failed_participant_send_retries_three_times_without_blocking_others",
        ],
        "failed reminder recipient is retried at most three times and notifies admin": [
            "test_failed_participant_send_retries_three_times_without_blocking_others",
            "test_failed_reminder_after_retry_exhaustion_notifies_admin",
        ],
        "week close creates gray reports for active missing participants": [
            "test_week_close_creates_gray_reports_for_active_missing_participants",
            "test_week_close_includes_non_consenting_active_participants",
        ],
        "week close skips dropped and already reported participants": [
            "test_week_close_skips_dropped_and_already_reported_participants",
        ],
        "unfinished draft still receives gray report and remains in sqlite": [
            "test_week_close_preserves_unfinished_drafts",
            "tests/test_weekly_report_boundaries.py::test_late_report_never_writes_weekly_report_or_relations",
        ],
        "week close is idempotent and recovers from partial sheets failures": [
            "test_week_close_is_idempotent_on_rerun",
            "test_week_close_rerun_after_partial_failure_creates_only_missing_gray_rows",
        ],
        "week close does not notify participants about gray status": [
            "test_week_close_sends_aggregated_silent_notification_to_captain_and_tracker",
        ],
        "silent notification goes to captain and tracker by team": [
            "test_week_close_sends_aggregated_silent_notification_to_captain_and_tracker",
            "test_silent_notifications_are_scoped_to_team",
        ],
        "silent notification does not disclose drafts or other teams": [
            "test_silent_notifications_are_scoped_to_team",
            "test_silent_notification_does_not_include_draft_state",
        ],
        "missing captain or tracker chat id does not block week close and notifies admin": [
            "test_missing_captain_or_tracker_chat_id_notifies_admin_without_blocking_week_close",
        ],
        "late draft finalization keeps existing deadline behavior": [
            "tests/test_weekly_report_finalize.py::test_finalize_rejects_late_report_without_final_facts",
            "tests/test_weekly_report_boundaries.py::test_late_report_never_writes_weekly_report_or_relations",
        ],
    }
    local_tests = {name for name, value in globals().items() if name.startswith("test_") and callable(value)}

    assert all(requirement for requirement in covered_by)
    assert all(test_names for test_names in covered_by.values())
    for test_names in covered_by.values():
        for test_name in test_names:
            if "::" not in test_name:
                assert test_name in local_tests


def _service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    weekly_reports: list[dict[str, object]] | None = None,
    goals: list[dict[str, object]] | None = None,
    planned_steps: list[dict[str, object]] | None = None,
    weekly_focus: list[dict[str, object]] | None = None,
    failing_chat_ids: set[str] | None = None,
    failure_message: str | None = None,
    gateway: FakeSheetsGateway | None = None,
) -> tuple[SchedulerService, FakeSheetsGateway, "FailingBotClient", FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = gateway or FakeSheetsGateway(
        participants=participants,
        weekly_reports=weekly_reports or [],
        goals=goals or [],
        planned_steps=planned_steps or [],
        weekly_focus=weekly_focus or [],
    )
    main_bot = FailingBotClient(
        BotPurpose.MAIN,
        failing_chat_ids=failing_chat_ids or set(),
        failure_message=failure_message,
    )
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    return (
        SchedulerService(
            sheets=gateway,
            notification_router=router,
            repository=SchedulerJobRepository(db_path),
        ),
        gateway,
        main_bot,
        error_bot,
    )


def _participant(
    participant_id: str,
    telegram_id: int,
    *,
    consent: bool,
    status: str = "active",
    role: str = "participant",
    team_id: str = "T001",
    full_name: str | None = None,
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "team_id": team_id,
        "full_name": full_name or f"Participant {participant_id}",
        "consent_given": consent,
        "status": status,
        "role": role,
    }


def _goal(goal_id: str, participant_id: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": "Цель",
        "goal_description": "Описание цели",
        "goal_value_amount": "100000",
        "goal_value_currency": "RUB",
        "permission_condition": "Оплата получена",
        "goal_status": "active",
    }


def _step(
    step_id: str,
    participant_id: str,
    goal_id: str,
    number: int,
    title: str,
    status: str,
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": number,
        "step_title": title,
        "step_description": "",
        "step_status": status,
    }


def _service_with_notification_bot(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    teams: list[dict[str, object]],
    trackers: list[dict[str, object]],
) -> tuple[SchedulerService, FakeSheetsGateway, FailingBotClient, FakeBotClient, FakeBotClient]:
    service, gateway, main_bot, error_bot = _service(
        tmp_path,
        participants=participants,
        gateway=FakeSheetsGateway(participants=participants, teams=teams, trackers=trackers),
    )
    return service, gateway, main_bot, error_bot, service.notification_router.notification_bot


@dataclass
class FailingBotClient:
    purpose: BotPurpose
    failing_chat_ids: set[str] = field(default_factory=set)
    failure_message: str | None = None
    sent_messages: list[OutgoingMessage] = field(default_factory=list)
    attempts_by_chat_id: dict[str, int] = field(default_factory=dict)

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        buttons: tuple[object, ...] = (),
    ) -> OutgoingMessage:
        self.attempts_by_chat_id[chat_id] = self.attempts_by_chat_id.get(chat_id, 0) + 1
        if chat_id in self.failing_chat_ids:
            raise RuntimeError(self.failure_message or f"send failed for {chat_id}")
        message = OutgoingMessage(chat_id=chat_id, text=text, buttons=buttons)
        self.sent_messages.append(message)
        return message


class FailsOnceAfterFirstGrayGateway(FakeSheetsGateway):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._failed = False

    def append_weekly_report(self, row: dict[str, object]) -> None:
        if len(self.list_weekly_reports()) == 1 and not self._failed:
            self._failed = True
            raise RuntimeError("google sheets unavailable")
        super().append_weekly_report(row)
