import logging

import pytest

from app.bot.clients import BotPurpose, FakeBotClient
from app.runtime import _notify_polling_error, _polling_error_text
from app.sheets.gateway import FakeSheetsGateway
from tests.test_runtime_entrypoint import _router


def test_key_error_notification_identifies_safe_source_and_explains_missing_data():
    try:
        FakeSheetsGateway().mark_participant_bot_started(
            "PERSONAL_SECRET_ID", started_at="now"
        )
    except KeyError as error:
        text = _polling_error_text(
            event="telegram_update_dispatch_failed",
            error=error,
            update_id=798033015,
            consecutive_failures=None,
        )
    assert "source=app.sheets.gateway.mark_participant_bot_started:" in text
    assert "reason=missing_expected_data" in text
    assert "Причина:" in text and "Что проверить:" in text
    assert "798033015" in text and "PERSONAL_SECRET_ID" not in text


@pytest.mark.parametrize(
    "error",
    [
        KeyError("private answer token=123456:SECRET"),
        RuntimeError("private answer token=123456:SECRET"),
    ],
)
def test_generic_error_values_never_leak(error):
    text = _polling_error_text(
        event="telegram_update_dispatch_failed",
        error=error,
        update_id=5,
        consecutive_failures=None,
    )
    expected_reason = (
        "missing_expected_data"
        if isinstance(error, KeyError)
        else "unexpected_handler_failure"
    )
    expected_hint = (
        "check_handler_location_and_required_data"
        if isinstance(error, KeyError)
        else "inspect_handler_location_and_provider_status"
    )
    assert f"reason={expected_reason}" in text and f"hint={expected_hint}" in text
    assert "source=unavailable" in text
    assert "Причина:" in text and "Что проверить:" in text
    assert "private" not in text and "SECRET" not in text and "token" not in text


def test_missing_report_draft_has_specific_safe_explanation():
    text = _polling_error_text(
        event="telegram_update_dispatch_failed",
        error=KeyError("Active step report draft not found for telegram_id=PRIVATE"),
        update_id=5,
        consecutive_failures=None,
    )
    assert "reason=active_draft_missing" in text
    assert "черновик" in text and "заново" in text
    assert "PRIVATE" not in text


def test_successfully_delivered_error_is_also_logged(caplog):
    with caplog.at_level(logging.ERROR):
        assert _notify_polling_error(
            _router(error_bot=FakeBotClient(BotPurpose.ERROR)),
            event="telegram_update_dispatch_failed",
            error=KeyError("private answer"),
            update_id=798033015,
        )
    assert "798033015" in caplog.text
    assert "reason=missing_expected_data" in caplog.text
    assert "private answer" not in caplog.text


def test_notification_failure_does_not_log_chained_sensitive_exceptions(caplog):
    class FailingBot(FakeBotClient):
        def send_message(self, **kwargs):
            raise RuntimeError("notification secret token=987654:SECRET")

    with caplog.at_level(logging.ERROR):
        try:
            raise KeyError("participant private answer token=123456:PRIVATE")
        except KeyError as error:
            delivered = _notify_polling_error(
                _router(error_bot=FailingBot(BotPurpose.ERROR)),
                event="telegram_update_dispatch_failed",
                error=error,
                update_id=17,
            )
    assert delivered is False
    assert "update_id=17" in caplog.text
    assert "PRIVATE" not in caplog.text and "SECRET" not in caplog.text
    assert "Traceback" not in caplog.text
