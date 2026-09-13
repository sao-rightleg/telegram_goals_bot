from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.bot.clients import BotPurpose, FakeBotClient
from app.reports.pdf import LocalPdfRenderer
from app.reports.service import ReportService
from app.scheduler.calendar import TIMEZONE_NAME
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.sheets.gateway import FakeSheetsGateway
from app.storage.paths import StoragePathPolicy
from app.storage.reports import ReportStateRepository
from app.storage.sqlite import initialize_schema


NOW = datetime(2026, 7, 12, 23, 59, tzinfo=ZoneInfo(TIMEZONE_NAME))


def test_generate_and_send_week_orchestrates_reports_from_final_sheets_facts(tmp_path: Path) -> None:
    service, _repository, _error_bot, notification_bot = _service(tmp_path)

    result = service.generate_and_send_week(5, now=NOW)

    assert result.generated_count >= 4
    assert result.sent_count >= 4
    assert any("Итоги недели 5" in message.text for message in notification_bot.sent_messages)
    assert notification_bot.sent_documents
    assert notification_bot.sent_documents[0].file_path.exists()


def test_report_job_run_uses_week_idempotency_key(tmp_path: Path) -> None:
    service, repository, _error_bot, _notification_bot = _service(tmp_path)

    service.generate_and_send_week(5, now=NOW)
    second = repository.start_job_run(
        week_number=5,
        idempotency_key="reports:FLOW_TEST:week_05",
        started_at=NOW.isoformat(),
    )

    assert second == 1


def test_report_service_returns_generated_sent_skipped_failed_counts(tmp_path: Path) -> None:
    service, _repository, _error_bot, _notification_bot = _service(tmp_path)

    first = service.generate_and_send_week(5, now=NOW)
    second = service.generate_and_send_week(5, now=NOW)

    assert first.sent_count > 0
    assert second.skipped_count == first.sent_count
    assert second.failed_count == 0


def test_pdf_generation_failure_notifies_admin_and_continues_other_teams(tmp_path: Path) -> None:
    service, _repository, error_bot, notification_bot = _service(
        tmp_path,
        pdf_renderer=FailingOneTeamPdfRenderer(
            LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))
        ),
    )

    result = service.generate_and_send_week(5, now=NOW)

    assert result.failed_count >= 1
    assert any("report_pdf_generation_failed" in message.text for message in error_bot.sent_messages)
    assert notification_bot.sent_messages


def test_report_service_marks_job_failed_when_unrecoverable_error_occurs(tmp_path: Path) -> None:
    service, repository, _error_bot, _notification_bot = _service(
        tmp_path,
        sheets_gateway=FailingSheetsGateway(),
    )

    result = service.generate_and_send_week(5, now=NOW)

    assert result.failed_count == 1
    run_id = repository.start_job_run(
        week_number=5,
        idempotency_key="reports:FLOW_TEST:week_05",
        started_at=NOW.isoformat(),
    )
    assert run_id == 1


def test_report_service_does_not_read_sqlite_drafts_as_content(tmp_path: Path) -> None:
    service, _repository, _error_bot, notification_bot = _service(tmp_path)

    service.generate_and_send_week(5, now=NOW)

    rendered_text = "\n".join(message.text for message in notification_bot.sent_messages)
    assert "черновик" not in rendered_text.lower()
    assert "draft" not in rendered_text.lower()


def test_report_service_renders_each_tracker_pdf_with_assigned_teams_only(tmp_path: Path) -> None:
    renderer = CapturingPdfRenderer(
        LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf"))
    )
    service, _repository, _error_bot, _notification_bot = _service(tmp_path, pdf_renderer=renderer)

    service.generate_and_send_week(5, now=NOW)

    assert renderer.tracker_team_ids == {
        "TR_MALE": ("T001",),
        "TR_FEMALE": ("T002",),
    }


def test_report_service_sends_one_role_specific_telegram_summary_per_recipient(tmp_path: Path) -> None:
    service, _repository, _error_bot, notification_bot = _service(tmp_path)

    service.generate_and_send_week(5, now=NOW)

    texts_by_chat = {
        chat_id: [message.text for message in notification_bot.sent_messages if message.chat_id == chat_id]
        for chat_id in ("2001", "2002", "3001", "3002", "9001", "9002")
    }
    assert all(len(messages) == 1 for messages in texts_by_chat.values())
    assert "Команда А" in texts_by_chat["3001"][0]
    assert "Команда Б" not in texts_by_chat["3001"][0]
    assert "Команда Б" in texts_by_chat["3002"][0]
    assert "Команда А" not in texts_by_chat["3002"][0]
    assert "Полные итоги" in texts_by_chat["9001"][0]
    assert "Результаты команд" in texts_by_chat["9002"][0]


def test_duplicate_active_tracker_id_is_rejected_without_pdf_delivery(tmp_path: Path) -> None:
    duplicate_trackers = [
        {"tracker_id": "TR_DUP", "telegram_id": 3001, "gender_scope": "male", "is_active": True},
        {"tracker_id": "TR_DUP", "telegram_id": 3002, "gender_scope": "female", "is_active": True},
    ]
    service, _repository, error_bot, notification_bot = _service(
        tmp_path, sheets_gateway=_gateway(trackers=duplicate_trackers)
    )

    result = service.generate_and_send_week(5, now=NOW)

    assert result.failed_count >= 1
    assert any("duplicate active tracker_id" in item.text for item in error_bot.sent_messages)
    assert all(document.chat_id not in {"3001", "3002"} for document in notification_bot.sent_documents)


def _service(
    tmp_path: Path,
    *,
    pdf_renderer: object | None = None,
    sheets_gateway: object | None = None,
) -> tuple[ReportService, ReportStateRepository, FakeBotClient, FakeBotClient]:
    from app.reports.delivery import ReportDeliveryService

    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = ReportStateRepository(db_path)
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    notification_bot = FakeBotClient(BotPurpose.NOTIFICATION)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=notification_bot,
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "admin-errors"),
    )
    delivery_service = ReportDeliveryService(repository=repository, notification_router=router)
    service = ReportService(
        sheets_gateway=sheets_gateway or _gateway(),
        report_repository=repository,
        pdf_renderer=pdf_renderer or LocalPdfRenderer(StoragePathPolicy(pdf_root=tmp_path / "reports" / "pdf")),
        delivery_service=delivery_service,
        flow_id="FLOW_TEST",
    )
    return service, repository, error_bot, notification_bot


def _gateway(*, trackers: list[dict[str, object]] | None = None) -> FakeSheetsGateway:
    return FakeSheetsGateway(
        teams=[
            {"team_id": "T001", "team_name": "Команда А", "gender": "male", "captain_id": "C001"},
            {"team_id": "T002", "team_name": "Команда Б", "gender": "female", "captain_id": "C002"},
        ],
        participants=[
            _participant("P001", "Анна Иванова", "participant", "T001", "active"),
            _participant("P002", "Пётр Смирнов", "participant", "T002", "active"),
            _participant("C001", "Ирина Капитан", "captain", "T001", "active", telegram_id=2001),
            _participant("C002", "Мария Капитан", "captain", "T002", "active", telegram_id=2002),
            _participant("A001", "Админ", "admin", None, "active", telegram_id=9001),
            _participant("S001", "Александр Ситников", "sitnikov", None, "active", telegram_id=9002),
        ],
        trackers=trackers or [
            {"tracker_id": "TR_MALE", "telegram_id": 3001, "gender_scope": "male", "is_active": True},
            {"tracker_id": "TR_FEMALE", "telegram_id": 3002, "gender_scope": "female", "is_active": True},
        ],
        goals=[
            _goal("G001", "P001", "Контракт"),
            _goal("G002", "P002", "Выступление"),
        ],
        planned_steps=[
            _step("S001", "P001", "G001", 1, "Найти клиента", "closed"),
            _step("S002", "P002", "G002", 1, "Подготовить тезисы", "partial"),
        ],
        weekly_reports=[
            _weekly_report("WR001", "P001", "T001", "G001", "green", "🟩", 1, "Провела встречу."),
            _weekly_report("WR002", "P002", "T002", "G002", "blue", "🟦", 0.5, "Подготовил тезисы."),
        ],
        insights=[
            {"insight_id": "I001", "participant_id": "P001", "week_number": 5, "insight_text": "Инсайт"},
        ],
    )


def _participant(
    participant_id: str,
    full_name: str,
    role: str,
    team_id: str | None,
    status: str,
    *,
    telegram_id: int = 1001,
) -> dict[str, object]:
    return {
        "participant_id": participant_id,
        "telegram_id": telegram_id,
        "username": participant_id.lower(),
        "full_name": full_name,
        "role": role,
        "team_id": team_id,
        "team_name": "Команда",
        "captain_id": "C001",
        "tracker_id": "TR001",
        "status": status,
    }


def _goal(goal_id: str, participant_id: str, title: str) -> dict[str, object]:
    return {
        "goal_id": goal_id,
        "participant_id": participant_id,
        "goal_title": title,
        "goal_description": title,
        "goal_value_amount": "100000",
        "goal_value_currency": "RUB",
        "permission_condition": "Готово",
        "goal_status": "active",
    }


def _step(
    step_id: str,
    participant_id: str,
    goal_id: str,
    step_number: int,
    title: str,
    status: str,
) -> dict[str, object]:
    return {
        "step_id": step_id,
        "participant_id": participant_id,
        "goal_id": goal_id,
        "step_number": step_number,
        "step_title": title,
        "step_status": status,
    }


def _weekly_report(
    report_id: str,
    participant_id: str,
    team_id: str,
    goal_id: str,
    status_code: str,
    status_symbol: str,
    score: int | float,
    text: str,
) -> dict[str, object]:
    return {
        "weekly_report_id": report_id,
        "participant_id": participant_id,
        "team_id": team_id,
        "goal_id": goal_id,
        "week_number": 5,
        "status_code": status_code,
        "status_symbol": status_symbol,
        "status_score": score,
        "report_text": text,
        "transcription_text": "",
    }


@dataclass(frozen=True)
class FailingOneTeamPdfRenderer:
    wrapped: LocalPdfRenderer

    def render_team_report(self, report: object, *, year: int = 2026) -> object:
        if getattr(report, "team_id") == "T001":
            raise RuntimeError("pdf renderer failed token=secret")
        return self.wrapped.render_team_report(report, year=year)

    def render_tracker_report(self, *args: object, **kwargs: object) -> object:
        return self.wrapped.render_tracker_report(*args, **kwargs)

    def render_full_report(self, *args: object, **kwargs: object) -> object:
        return self.wrapped.render_full_report(*args, **kwargs)


@dataclass
class CapturingPdfRenderer:
    wrapped: LocalPdfRenderer
    tracker_team_ids: dict[str, tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        self.tracker_team_ids = {}

    def render_team_report(self, *args: object, **kwargs: object) -> object:
        return self.wrapped.render_team_report(*args, **kwargs)

    def render_tracker_report(self, teams: object, **kwargs: object) -> object:
        team_tuple = tuple(teams)
        assert self.tracker_team_ids is not None
        self.tracker_team_ids[str(kwargs["tracker_id"])] = tuple(team.team_id for team in team_tuple)
        return self.wrapped.render_tracker_report(team_tuple, **kwargs)

    def render_full_report(self, *args: object, **kwargs: object) -> object:
        return self.wrapped.render_full_report(*args, **kwargs)


class FailingSheetsGateway:
    def list_teams(self) -> list[dict[str, object]]:
        raise RuntimeError("sheets unavailable")
