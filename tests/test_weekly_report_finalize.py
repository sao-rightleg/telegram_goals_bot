from dataclasses import replace
from pathlib import Path

from app.bot.clients import TelegramInlineButton
from app.bot.menus import WEEKLY_REPORT_DONE_CALLBACK
from app.bot.messages import VOICE_ACCEPTED_TEXT, WEEKLY_REPORT_EMPTY_TEXT, WEEKLY_REPORT_LATE_TEXT
from app.services.voice_messages import StoredVoiceAttachment, VoiceMessageInput, VoiceMessageResult
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
            "weekly_report_id": "WR:P001:week-04:step-S001",
            "participant_id": "P001",
            "team_id": "T001",
            "goal_id": "G001",
            "week_number": 4,
            "status_code": "green",
            "status_symbol": "🟩",
            "score": 1,
            "report_text": "Сделал первый шаг",
            "transcription_text": "",
            "audio_file_path": "",
            "audio_deleted_at": "",
            "submitted_at": NOW.isoformat(),
            "submitted_by_id": "P001",
            "submitted_by_role": "participant",
            "flow_source": "participant_bot",
        }
    ]
    assert gateway.list_weekly_report_steps() == [
        {
            "weekly_report_step_id": "WRS:WR:P001:week-04:step-S001:S001",
            "weekly_report_id": "WR:P001:week-04:step-S001",
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


def test_add_text_message_returns_done_button(tmp_path: Path) -> None:
    service, _gateway, _drafts, main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service.start_report(user, now=NOW)
    service.select_status(user, WeeklyReportStatus.RED, now=NOW)

    response = service.add_text_message(user, "Не успел", now=NOW)

    assert response.text == "Текст добавлен. Можно отправить ещё или нажать «✅ Отчёт готов»."
    assert response.buttons == (
        TelegramInlineButton(text="✅ Отчёт готов", callback_data=WEEKLY_REPORT_DONE_CALLBACK),
    )
    assert main_bot.sent_messages[-1].buttons == response.buttons


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


def test_voice_report_final_save_includes_transcription_and_audio_path(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    drafts.append_voice_transcription(
        user.telegram_id,
        telegram_file_id="telegram-file-1",
        local_file_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"),
        duration_seconds=42,
        transcription_text="Голосовой отчёт",
        occurred_at=NOW.isoformat(),
        telegram_message_id=501,
    )

    service.finalize_report(user, now=NOW)

    row = gateway.list_weekly_reports()[0]
    assert row["report_text"] == "Голосовой отчёт"
    assert row["transcription_text"] == "Голосовой отчёт"
    assert row["audio_file_path"] == "data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"
    assert row["audio_deleted_at"] == ""


def test_mixed_text_and_voice_report_preserves_order(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Первое", now=NOW, telegram_message_id=501)
    drafts.append_voice_transcription(
        user.telegram_id,
        telegram_file_id="telegram-file-1",
        local_file_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_502.ogg"),
        duration_seconds=42,
        transcription_text="Голосом второе",
        occurred_at=NOW.isoformat(),
        telegram_message_id=502,
    )
    service.add_text_message(user, "Третье", now=NOW, telegram_message_id=503)

    service.finalize_report(user, now=NOW)

    row = gateway.list_weekly_reports()[0]
    assert row["report_text"] == "Первое\nГолосом второе\nТретье"
    assert row["transcription_text"] == "Голосом второе"
    assert row["audio_file_path"] == "data/audio/2026/week_04/T001/P001/voice_1001_502.ogg"
    assert row["audio_deleted_at"] == ""


def test_finalize_rejects_late_report_without_final_facts(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Сделал", now=NOW)

    response = service.finalize_report(user, now=LATE)

    assert response.text == WEEKLY_REPORT_LATE_TEXT
    assert gateway.list_weekly_reports() == []
    assert drafts.get_active_draft(1001) is not None


def test_finalize_rejects_duplicate_step_report_without_final_facts(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    _prepare_green(service, user)
    service.add_text_message(user, "Сделал", now=NOW)
    gateway.append_weekly_report(
        {"weekly_report_id": "WR:P001:week-04:step-S001", "participant_id": "P001", "week_number": 4}
    )
    gateway.append_weekly_report_step(
        {
            "weekly_report_step_id": "WRS:WR:P001:week-04:step-S001:S001",
            "weekly_report_id": "WR:P001:week-04:step-S001",
            "participant_id": "P001",
            "step_id": "S001",
        }
    )

    response = service.finalize_report(user, now=NOW)

    assert response.text == "По этому шагу отчёт уже сохранён. Нажми «Редактировать отчёт»."
    assert len(gateway.list_weekly_reports()) == 1
    assert drafts.get_active_draft(1001) is not None


def test_edit_step_report_updates_text_without_reclosing_step(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot, _error_bot = _service(
        tmp_path,
        planned_steps=[
            {
                "step_id": "S001",
                "participant_id": "P001",
                "goal_id": "G001",
                "step_number": 1,
                "step_title": "Первый шаг",
                "step_status": "closed",
                "closed_week_number": 4,
                "closed_report_id": "WR:P001:week-04:step-S001",
                "closed_at": "2026-07-01T10:00:00+05:00",
            }
        ],
        weekly_reports=[
            {
                "weekly_report_id": "WR:P001:week-04:step-S001",
                "participant_id": "P001",
                "team_id": "T001",
                "goal_id": "G001",
                "week_number": 4,
                "status_code": "green",
                "status_symbol": "🟩",
                "score": 1,
                "report_text": "Старый текст",
                "transcription_text": "",
                "audio_file_path": "",
                "submitted_at": "2026-07-01T10:00:00+05:00",
                "updated_at": "2026-07-01T10:00:00+05:00",
            }
        ],
        weekly_report_steps=[
            {
                "weekly_report_step_id": "WRS:WR:P001:week-04:step-S001:S001",
                "weekly_report_id": "WR:P001:week-04:step-S001",
                "participant_id": "P001",
                "step_id": "S001",
            }
        ],
    )
    user = _user()

    service.start_edit_report_for_step(user, step_id="S001", now=NOW)
    service.add_text_message(user, "Новый текст", now=NOW)
    response = service.finalize_report(user, now=NOW)

    assert response.text == "Отчёт по шагу обновлён."
    assert drafts.get_active_draft(1001) is None
    assert len(gateway.list_weekly_reports()) == 1
    report = gateway.list_weekly_reports()[0]
    assert report["report_text"] == "Новый текст"
    assert report["submitted_at"] == "2026-07-01T10:00:00+05:00"
    assert report["updated_at"] == NOW.isoformat()
    step = gateway.list_planned_steps("P001", "G001")[0]
    assert step["closed_at"] == "2026-07-01T10:00:00+05:00"
    assert step["closed_week_number"] == 4


def test_voice_message_appends_to_weekly_draft(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot, _error_bot = _service(tmp_path)
    user = _user()
    service = replace(service, voice_messages=AcceptingVoiceService(drafts=drafts))
    service.start_report(user, now=NOW)

    response = service.add_voice_message(
        user,
        telegram_file_id="telegram-file-1",
        duration_seconds=42,
        now=NOW,
        telegram_message_id=501,
    )

    assert response.text == VOICE_ACCEPTED_TEXT
    assert drafts.get_active_draft(1001).report_text == "Голосовой отчёт"


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


class AcceptingVoiceService:
    def __init__(self, drafts) -> None:
        self._drafts = drafts

    def handle_voice(self, request: VoiceMessageInput) -> VoiceMessageResult:
        self._drafts.append_voice_transcription(
            request.user.telegram_id,
            telegram_file_id=request.telegram_file_id,
            local_file_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"),
            duration_seconds=request.duration_seconds,
            transcription_text="Голосовой отчёт",
            occurred_at=request.now.isoformat(),
            telegram_message_id=request.telegram_message_id,
        )
        return VoiceMessageResult(
            text=VOICE_ACCEPTED_TEXT,
            accepted=True,
            attachment=StoredVoiceAttachment(
                local_file_path=Path("data/audio/2026/week_04/T001/P001/voice_1001_501.ogg"),
                transcription_text="Голосовой отчёт",
                duration_seconds=request.duration_seconds,
            ),
        )
