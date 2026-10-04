from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from app.bot.menus import MenuAction
from app.services.participant_models import TelegramUserContext
from app.sheets.gateway import GoogleSheetsError
from app.domain import MAX_EXACT_WORD_PRICE_RUB
from app.storage.dialog_state import DialogStateRepository
from app.storage.step_drafts import StepDraftRepository
from tests.test_participant_step_setup_flow import NOW, _service
from tests.test_runtime_entrypoint import _dispatcher, _message_update


USER = TelegramUserContext(telegram_id=1001, chat_id="1001")


def _save_steps(service):
    service.handle_menu_action(USER, MenuAction.VIEW_STEPS, occurred_at=NOW)
    for number in range(1, 9):
        service.handle_steps_text(USER, f"Шаг {number}", occurred_at=NOW)
        service.handle_steps_text(USER, f"Метрика {number}", occurred_at=NOW)
    return service.confirm_steps(USER, occurred_at=NOW)


def test_step_confirmation_prompts_word_price(tmp_path: Path) -> None:
    service, gateway, drafts, _bot = _service(tmp_path)
    response = _save_steps(service)
    assert "Какова твоя цена слова" in response.text
    assert "целое число рублей больше нуля" in response.text
    assert service.dialog_states.get(1001).step == "awaiting_word_price"
    assert len(gateway.list_planned_steps("P001", "G001")) == 8
    assert drafts.get(1001) is None


@pytest.mark.parametrize(
    "text",
    ["", " ", "0", "-1", "1.5", "1,5", "5000 руб", "+5", "1e3", "²", "９", "9" * 5000],
)
def test_invalid_word_price_keeps_question_active(tmp_path: Path, text: str) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    response = service.handle_steps_text(USER, text, occurred_at=NOW)
    assert "целое число рублей больше нуля" in response.text
    assert service.dialog_states.get(1001).step == "awaiting_word_price"
    assert gateway.find_word_price("F001", "P001") is None


def test_word_price_is_saved_for_the_participant_and_flow(tmp_path: Path) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    response = service.handle_steps_text(USER, " 005000 ", occurred_at=NOW)
    assert gateway.find_word_price("F001", "P001") == {
        "flow_id": "F001",
        "participant_id": "P001",
        "word_price_rub": 5000,
        "created_at": NOW,
        "updated_at": NOW,
    }
    assert "5000" in response.text
    assert service.dialog_states.get(1001).flow == "idle"


def test_start_resumes_word_price_after_restart_and_setup_deadline(
    tmp_path: Path,
) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    service = replace(
        service,
        dialog_states=DialogStateRepository(tmp_path / "state.sqlite3"),
        step_drafts=StepDraftRepository(tmp_path / "state.sqlite3"),
    )
    later = "2026-09-27T10:00:00+05:00"
    response = service.handle_start(USER, occurred_at=later)
    assert "Какова твоя цена слова" in response.text
    service.handle_steps_text(USER, "1", occurred_at=later)
    assert gateway.find_word_price("F001", "P001")["word_price_rub"] == 1


def test_write_failure_retains_question_and_retry_saves_once(tmp_path: Path) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    save = gateway.save_word_price

    def fail(row):
        save(row)
        raise GoogleSheetsError("response lost after append")

    gateway.save_word_price = fail
    with pytest.raises(GoogleSheetsError):
        service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert service.dialog_states.get(1001).step == "awaiting_word_price"
    gateway.save_word_price = save
    service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert len(gateway._word_prices) == 1


def test_other_participant_state_cannot_save_price(tmp_path: Path) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    state = service.dialog_states.get(1001)
    service.dialog_states.upsert(replace(state, participant_id="P_OTHER"))
    with pytest.raises(ValueError):
        service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert gateway.find_word_price("F001", "P001") is None


def test_saved_price_is_not_requested_or_overwritten_on_repeated_confirmation(
    tmp_path: Path,
) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    service.handle_steps_text(USER, "5000", occurred_at=NOW)
    response = service.confirm_steps(USER, occurred_at=NOW)
    assert response.text == "Восемь шагов уже сохранены."
    assert len(gateway._word_prices) == 1


@pytest.mark.parametrize("action", ["edit", "cancel", "menu"])
def test_stale_step_controls_cannot_skip_price_or_recreate_plan(
    tmp_path: Path, action: str
) -> None:
    service, gateway, drafts, _bot = _service(tmp_path)
    _save_steps(service)
    if action == "edit":
        response = service.edit_step_draft(USER, step_number=1, occurred_at=NOW)
    elif action == "cancel":
        response = service.cancel_steps(USER, occurred_at=NOW)
    else:
        response = service.handle_menu_action(
            USER, MenuAction.VIEW_STEPS, occurred_at=NOW
        )
    assert "Какова твоя цена слова" in response.text
    assert service.dialog_states.get(1001).step == "awaiting_word_price"
    assert drafts.get(1001) is None
    assert len(gateway.list_planned_steps("P001", "G001")) == 8


@pytest.mark.parametrize(
    "amount,accepted",
    [
        (1, True),
        (MAX_EXACT_WORD_PRICE_RUB, True),
        (MAX_EXACT_WORD_PRICE_RUB + 1, False),
    ],
)
def test_word_price_numeric_storage_boundary(
    tmp_path: Path, amount: int, accepted: bool
) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    response = service.handle_steps_text(USER, str(amount), occurred_at=NOW)
    saved = gateway.find_word_price("F001", "P001")
    if accepted:
        assert saved["word_price_rub"] == amount
    else:
        assert saved is None
        assert "целое число рублей больше нуля" in response.text


def test_telegram_dispatcher_routes_price_answer_to_real_service(
    tmp_path: Path,
) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    dispatcher, _services, _error_bot = _dispatcher(tmp_path)
    dispatcher = replace(
        dispatcher,
        participant_service=service,
        now_provider=lambda: datetime.fromisoformat(NOW),
    )
    invalid = dispatcher.dispatch_update(_message_update(text="0"))
    assert "целое число рублей больше нуля" in invalid.text
    dispatcher.dispatch_update(_message_update(text="5000", update_id=11))
    dispatcher.dispatch_update(_message_update(text="5000", update_id=12))
    assert gateway.find_word_price("F001", "P001")["word_price_rub"] == 5000
    assert len(gateway._word_prices) == 1


def test_failure_before_save_preserves_pending_question(tmp_path: Path) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    save = gateway.save_word_price

    def fail(row):
        raise GoogleSheetsError("provider unavailable")

    gateway.save_word_price = fail
    with pytest.raises(GoogleSheetsError):
        service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert gateway.find_word_price("F001", "P001") is None
    assert service.dialog_states.get(1001).step == "awaiting_word_price"
    gateway.save_word_price = save
    service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert len(gateway._word_prices) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("consent_given", False),
        ("status", "dropped"),
        ("role", "tracker"),
        ("team_id", ""),
    ],
)
def test_ineligible_participant_cannot_save_word_price(
    tmp_path: Path, field: str, value: object
) -> None:
    service, gateway, _drafts, _bot = _service(tmp_path)
    _save_steps(service)
    gateway._participants[0][field] = value
    with pytest.raises(ValueError):
        service.handle_steps_text(USER, "5000", occurred_at=NOW)
    assert gateway.find_word_price("F001", "P001") is None
