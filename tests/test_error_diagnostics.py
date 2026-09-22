import re

import pytest

from app.errors import (
    ActionDiagnosticError,
    ActionDiagnosticKind,
    action_diagnostic_explanation,
)


def test_every_action_diagnostic_uses_fixed_machine_codes_and_russian_explanation() -> None:
    safe_code = re.compile(r"^[a-z_]+$")

    for kind in ActionDiagnosticKind:
        error = ActionDiagnosticError(kind)

        assert safe_code.fullmatch(error.action)
        assert safe_code.fullmatch(error.reason)
        assert safe_code.fullmatch(error.hint)
        explanation = action_diagnostic_explanation(error)
        assert explanation.startswith("Причина: ")
        assert ". Что проверить: " in explanation


def test_action_diagnostic_rejects_unregistered_dynamic_value() -> None:
    with pytest.raises(KeyError):
        ActionDiagnosticError("Имя участника secret-token")  # type: ignore[arg-type]
