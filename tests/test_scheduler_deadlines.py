from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.bot.clients import BotPurpose, FakeBotClient, OutgoingMessage
from app.scheduler.calendar import TIMEZONE_NAME
from app.scheduler.jobs import SchedulerService
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import FakeSheetsGateway
from app.storage.scheduler import SchedulerJobRepository
from app.storage.sqlite import initialize_schema


NOW = datetime(2026, 7, 2, 10, 0, tzinfo=ZoneInfo(TIMEZONE_NAME))


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


def _service(
    tmp_path: Path,
    *,
    participants: list[dict[str, object]],
    weekly_reports: list[dict[str, object]] | None = None,
    failing_chat_ids: set[str] | None = None,
) -> tuple[SchedulerService, FakeSheetsGateway, "FailingBotClient", FakeBotClient]:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(participants=participants, weekly_reports=weekly_reports or [])
    main_bot = FailingBotClient(BotPurpose.MAIN, failing_chat_ids=failing_chat_ids or set())
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
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "team_id": "T001",
        "full_name": f"Participant {participant_id}",
        "consent_given": consent,
        "status": status,
    }


@dataclass
class FailingBotClient:
    purpose: BotPurpose
    failing_chat_ids: set[str] = field(default_factory=set)
    sent_messages: list[OutgoingMessage] = field(default_factory=list)
    attempts_by_chat_id: dict[str, int] = field(default_factory=dict)

    def send_message(self, *, chat_id: str, text: str) -> OutgoingMessage:
        self.attempts_by_chat_id[chat_id] = self.attempts_by_chat_id.get(chat_id, 0) + 1
        if chat_id in self.failing_chat_ids:
            raise RuntimeError(f"send failed for {chat_id}")
        message = OutgoingMessage(chat_id=chat_id, text=text)
        self.sent_messages.append(message)
        return message
