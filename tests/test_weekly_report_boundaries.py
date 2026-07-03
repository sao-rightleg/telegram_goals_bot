import ast
import sqlite3
from dataclasses import replace
from pathlib import Path

from app.bot.messages import WEEKLY_REPORT_LATE_TEXT
from app.services.voice_messages import VoiceMessageInput, VoiceMessageResult
from app.services.weekly_report_models import WeeklyReportStatus
from app.storage.sqlite import BUSINESS_PRIMARY_TABLES, list_tables

from tests.test_weekly_report_start_flow import LATE, NOW, _service, _step, _user


def test_participant_cannot_select_another_participants_step(tmp_path: Path) -> None:
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


def test_late_report_never_writes_weekly_report_or_relations(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)
    service.select_steps(user, ["S001"], now=NOW)
    service.add_text_message(user, "Сделал", now=NOW)

    response = service.finalize_report(user, now=LATE)

    assert response.text == "Дедлайн недели уже прошёл. Отчёт не может изменить статус."
    assert gateway.list_weekly_reports() == []
    assert gateway.list_weekly_report_steps() == []
    assert gateway.list_planned_steps("P001", "G001")[0]["step_status"] == "open"
    assert drafts.get_active_draft(1001) is not None


def test_duplicate_report_never_writes_second_report_or_relations(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.GREEN, now=NOW)
    service.select_steps(user, ["S001"], now=NOW)
    service.add_text_message(user, "Сделал", now=NOW)
    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4})

    response = service.finalize_report(user, now=NOW)

    assert response.text == "Отчёт за эту неделю уже принят."
    assert gateway.list_weekly_reports() == [
        {"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4}
    ]
    assert gateway.list_weekly_report_steps() == []
    assert drafts.get_active_draft(1001) is not None


def test_voice_does_not_bypass_deadline_or_duplicate_guards(tmp_path: Path) -> None:
    late_service, _late_gateway, late_drafts, _main_bot, _error_bot = _service(tmp_path / "late")
    late_service = replace(late_service, voice_messages=ExplodingVoiceService())
    late_user = _user()
    late_service.start_report(late_user, now=NOW)

    late_response = late_service.add_voice_message(
        late_user,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        now=LATE,
        telegram_message_id=501,
    )

    assert late_response.text == WEEKLY_REPORT_LATE_TEXT
    assert late_drafts.get_active_draft(1001).message_count == 0

    duplicate_service, gateway, duplicate_drafts, _main_bot, _error_bot = _service(tmp_path / "duplicate")
    duplicate_service = replace(duplicate_service, voice_messages=ExplodingVoiceService())
    duplicate_user = _user()
    duplicate_service.start_report(duplicate_user, now=NOW)
    gateway.append_weekly_report({"weekly_report_id": "WR001", "participant_id": "P001", "week_number": 4})

    duplicate_response = duplicate_service.add_voice_message(
        duplicate_user,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        now=NOW,
        telegram_message_id=501,
    )

    assert duplicate_response.text == "Отчёт за эту неделю уже принят."
    assert duplicate_drafts.get_active_draft(1001).message_count == 0


def test_invalid_draft_recovery_clears_state_and_notifies_admin(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)

    response = service.recover_invalid_draft(user, reason="stale_draft", now=NOW)

    assert response.text == "Черновик отчёта сброшен. Начни отправку отчёта заново."
    assert drafts.get_active_draft(1001) is None
    assert "invalid_weekly_report_draft" in error_bot.sent_messages[-1].text
    assert "stale_draft" in error_bot.sent_messages[-1].text
    assert "token" not in error_bot.sent_messages[-1].text.lower()


def test_missing_goal_or_steps_sends_safe_admin_notification(tmp_path: Path) -> None:
    service, _gateway, _drafts, main_bot, error_bot = _service(tmp_path, planned_steps=[])

    response = service.start_report(_user(), now=NOW)

    assert response.text == "Данные пока не заполнены. Свяжитесь со своим капитаном."
    assert main_bot.sent_messages[-1].text == response.text
    assert "missing_required_data" in error_bot.sent_messages[-1].text
    assert "planned_steps" in error_bot.sent_messages[-1].text
    assert "token" not in error_bot.sent_messages[-1].text.lower()
    assert "Сделал" not in error_bot.sent_messages[-1].text


def test_weekly_report_feature_does_not_add_out_of_scope_runtime_boundaries(tmp_path: Path) -> None:
    forbidden_import_roots = {
        "aiogram",
        "telegram",
        "google",
        "gspread",
        "reportlab",
        "weasyprint",
        "openai",
        "whisper",
        "docker",
        "celery",
        "redis",
    }
    checked_paths = [
        Path("app/services/weekly_reports.py"),
        Path("app/storage/weekly_report_drafts.py"),
        Path("app/sheets/gateway.py"),
    ]

    for module_path in checked_paths:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        imports = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imports.update(
            node.module.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )

        assert imports.isdisjoint(forbidden_import_roots), module_path

    db_path = tmp_path / "state.sqlite3"
    service, _gateway, _drafts, _main_bot, _error_bot = _service(tmp_path)
    service.start_report(_user(), now=NOW)

    with sqlite3.connect(db_path) as connection:
        attachment_count = connection.execute("SELECT COUNT(*) FROM draft_attachments").fetchone()[0]

    assert attachment_count == 0
    assert list_tables(db_path).isdisjoint(BUSINESS_PRIMARY_TABLES)


class ExplodingVoiceService:
    def handle_voice(self, request: VoiceMessageInput) -> VoiceMessageResult:
        raise AssertionError("voice service should not run after weekly report guard failure")
