from pathlib import Path

import pytest

from app.bot.clients import BotPurpose, FakeBotClient
from app.bot.menus import MenuAction
from app.services.notifications import NotificationRouter, Recipient, RecipientType
from app.services.participant_flows import ParticipantFlowService
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import FakeSheetsGateway
from app.storage.dialog_state import DialogStateRepository
from app.storage.sqlite import initialize_schema
from app.storage.step_drafts import StepDraftRepository


NOW = "2026-09-20T12:00:00+05:00"


def test_participant_records_exactly_eight_steps_with_metrics(tmp_path: Path) -> None:
    service, gateway, drafts, main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")

    started = service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    assert started.text == (
        "Сформулируем 8 шагов к твоей цели.\n\n"
        "Шаг 1 из 8. Опиши суть шага: что конкретно ты собираешься сделать?"
    )

    for number in range(1, 9):
        essence = service.handle_steps_text(
            user, f"Провести действие {number}", occurred_at=NOW
        )
        assert essence.text == (
            f"Шаг {number} из 8. Укажи измеримую метрику достижения этого шага."
        )
        metric = service.handle_steps_text(
            user, f"Не менее {number * 10} единиц", occurred_at=NOW
        )
        if number < 8:
            assert metric.text.endswith(
                f"Шаг {number + 1} из 8. Опиши суть шага: что конкретно ты собираешься сделать?"
            )

    draft = drafts.get(1001)
    assert draft is not None
    assert len(draft.items) == 8
    assert draft.items[7].description == "Провести действие 8"
    assert draft.items[7].metric == "Не менее 80 единиц"
    assert "Шаг 8. Провести действие 8" in metric.text
    assert [button.callback_data for button in metric.buttons][-2:] == [
        "steps:confirm",
        "steps:cancel",
    ]

    saved = service.confirm_steps(user, occurred_at=NOW)

    rows = gateway.list_planned_steps("P001", "G001")
    assert saved.text == "Восемь шагов сохранены."
    assert len(rows) == 8
    assert [row["step_number"] for row in rows] == list(range(1, 9))
    assert rows[0]["step_description"] == "Провести действие 1"
    assert rows[0]["step_metric"] == "Не менее 10 единиц"
    assert all(row["step_status"] == "open" for row in rows)
    assert drafts.get(1001) is None
    assert main_bot.sent_messages[-1].text == saved.text


def test_step_draft_can_edit_one_step_before_confirmation(tmp_path: Path) -> None:
    service, _gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    for number in range(1, 9):
        service.handle_steps_text(user, f"Суть {number}", occurred_at=NOW)
        service.handle_steps_text(user, f"Метрика {number}", occurred_at=NOW)

    edit = service.edit_step_draft(user, step_number=3, occurred_at=NOW)
    assert edit.text == "Шаг 3 из 8. Введи новую суть шага."
    service.handle_steps_text(user, "Новая суть", occurred_at=NOW)
    confirmation = service.handle_steps_text(user, "Новая метрика", occurred_at=NOW)

    assert drafts.get(1001).items[2].description == "Новая суть"  # type: ignore[union-attr]
    assert drafts.get(1001).items[2].metric == "Новая метрика"  # type: ignore[union-attr]
    assert "Шаг 3. Новая суть" in confirmation.text
    assert "Метрика: Новая метрика" in confirmation.text


def test_steps_cannot_be_created_without_active_goal_or_outside_window(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    gateway._goals.clear()  # test boundary: simulate missing business prerequisite

    missing = service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    assert missing.text == "Данные пока не заполнены. Свяжитесь со своим капитаном."
    assert drafts.get(1001) is None

    service, _gateway, drafts, _main_bot = _service(tmp_path / "closed")
    closed = service.handle_menu_action(
        user, MenuAction.VIEW_STEPS, occurred_at="2026-09-27T00:00:00+05:00"
    )
    assert closed.text == "Этап формирования шагов уже завершён."
    assert drafts.get(1001) is None


def test_step_confirmation_is_idempotent_and_write_failure_releases_draft(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    for number in range(1, 9):
        service.handle_steps_text(user, f"Суть {number}", occurred_at=NOW)
        service.handle_steps_text(user, f"Метрика {number}", occurred_at=NOW)

    original_append = gateway.append_planned_steps
    calls = 0

    def fail_once(rows):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("provider unavailable")
        original_append(rows)

    gateway.append_planned_steps = fail_once  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.confirm_steps(user, occurred_at=NOW)

    assert drafts.get(1001).status == "active"  # type: ignore[union-attr]
    service.confirm_steps(user, occurred_at=NOW)
    repeated = service.confirm_steps(user, occurred_at=NOW)

    assert repeated.text == "Восемь шагов уже сохранены."
    assert len(gateway.list_planned_steps("P001", "G001")) == 8


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("status", "dropped"),
        ("role", "tracker"),
        ("flow_id", "F999"),
    ],
)
def test_ineligible_participant_cannot_create_step_draft(
    tmp_path: Path, field: str, value: object
) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    gateway._participants[0][field] = value

    with pytest.raises(PermissionError):
        service.handle_menu_action(
            TelegramUserContext(telegram_id=1001, chat_id="1001"),
            MenuAction.VIEW_STEPS,
            occurred_at=NOW,
        )

    assert drafts.get(1001) is None
    assert gateway.list_planned_steps("P001", "G001") == []


def test_non_consenting_participant_gets_consent_flow_not_step_draft(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    gateway._participants[0]["consent_given"] = False

    response = service.handle_menu_action(
        TelegramUserContext(telegram_id=1001, chat_id="1001"),
        MenuAction.VIEW_STEPS,
        occurred_at=NOW,
    )

    assert "согласие" in response.text.lower()
    assert drafts.get(1001) is None
    assert gateway.list_planned_steps("P001", "G001") == []


def test_step_values_are_normalized_bounded_and_cancelled_cleanly(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)

    empty = service.handle_steps_text(user, "   ", occurred_at=NOW)
    too_long = service.handle_steps_text(user, "x" * 501, occurred_at=NOW)
    assert empty.text == "Ответ не должен быть пустым."
    assert too_long.text == "Сократи суть шага до 500 символов."
    assert drafts.get(1001).items == ()  # type: ignore[union-attr]

    service.handle_steps_text(user, "  Суть   шага  ", occurred_at=NOW)
    metric_long = service.handle_steps_text(user, "m" * 301, occurred_at=NOW)
    assert metric_long.text == "Сократи метрику до 300 символов."
    assert drafts.get(1001).items[0].description == "Суть шага"  # type: ignore[union-attr]

    cancelled = service.cancel_steps(user, occurred_at=NOW)
    assert cancelled.text == "Черновик шагов удалён."
    assert drafts.get(1001) is None
    assert gateway.list_planned_steps("P001", "G001") == []


def test_lost_dialog_resumes_scope_mismatch_restarts_and_busy_claim_does_not_write(
    tmp_path: Path,
) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    service.handle_steps_text(user, "Суть 1", occurred_at=NOW)
    service.dialog_states.clear(1001)

    resumed = service.handle_steps_text(user, "ignored", occurred_at=NOW)
    assert resumed.text == "Шаг 1 из 8. Укажи измеримую метрику достижения этого шага."

    drafts.create(
        telegram_id=1001, participant_id="P001", flow_id="F999",
        goal_id="G001", occurred_at=NOW,
    )
    restarted = service.handle_steps_text(user, "ignored", occurred_at=NOW)
    assert restarted.text.startswith("Сформулируем 8 шагов")
    assert drafts.get(1001).flow_id == "F001"  # type: ignore[union-attr]

    for number in range(1, 9):
        service.handle_steps_text(user, f"Суть {number}", occurred_at=NOW)
        service.handle_steps_text(user, f"Метрика {number}", occurred_at=NOW)
    drafts.claim = lambda *_args, **_kwargs: False  # type: ignore[method-assign]
    busy = service.confirm_steps(user, occurred_at=NOW)
    assert busy.text == "Шаги уже сохраняются. Подожди несколько секунд."
    assert gateway.list_planned_steps("P001", "G001") == []


def test_expired_step_draft_is_purged_with_its_items(tmp_path: Path) -> None:
    _service_instance, _gateway, drafts, _main_bot = _service(tmp_path)
    drafts.create(
        telegram_id=1001, participant_id="P001", flow_id="F001",
        goal_id="G001", occurred_at=NOW,
    )
    drafts.set_description(
        1001, step_number=1, description="Черновик", occurred_at=NOW
    )

    assert drafts.purge_expired(occurred_at="2026-10-04T12:00:00+05:00") == 0
    assert drafts.purge_expired(occurred_at="2026-10-04T12:00:01+05:00") == 1
    assert drafts.get(1001) is None


def test_stale_step_finalization_resumes_without_losing_completed_draft(tmp_path: Path) -> None:
    service, gateway, drafts, _main_bot = _service(tmp_path)
    user = TelegramUserContext(telegram_id=1001, chat_id="1001")
    service.handle_menu_action(user, MenuAction.VIEW_STEPS, occurred_at=NOW)
    for number in range(1, 9):
        service.handle_steps_text(user, f"Суть {number}", occurred_at=NOW)
        service.handle_steps_text(user, f"Метрика {number}", occurred_at=NOW)
    assert drafts.claim(1001, occurred_at=NOW) is True

    result = service.confirm_steps(user, occurred_at="2026-09-20T12:11:00+05:00")

    assert result.text == "Восемь шагов сохранены."
    assert len(gateway.list_planned_steps("P001", "G001")) == 8
    assert drafts.get(1001) is None

def _service(tmp_path: Path):
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    gateway = FakeSheetsGateway(
        participants=[{
            "participant_id": "P001", "telegram_id": 1001, "flow_id": "F001",
            "role": "participant", "status": "active", "team_id": "T001",
            "consent_given": True,
        }],
        goals=[{"goal_id": "G001", "participant_id": "P001", "goal_status": "active"}],
        challenge_flows=[{
            "flow_id": "F001", "flow_status": "active",
            "steps_setup_start_date": "2026-09-14",
            "steps_setup_end_date": "2026-09-26",
        }],
    )
    main_bot = FakeBotClient(BotPurpose.MAIN)
    error_bot = FakeBotClient(BotPurpose.ERROR)
    router = NotificationRouter(
        main_bot=main_bot,
        error_bot=error_bot,
        notification_bot=FakeBotClient(BotPurpose.NOTIFICATION),
        admin_error_recipient=Recipient(RecipientType.ADMIN_ERROR_CHAT, "errors"),
    )
    drafts = StepDraftRepository(db_path)
    service = ParticipantFlowService(
        sheets=gateway,
        main_bot=main_bot,
        notification_router=router,
        dialog_states=DialogStateRepository(db_path),
        registration_flows=gateway,
        step_drafts=drafts,
    )
    return service, gateway, drafts, main_bot
