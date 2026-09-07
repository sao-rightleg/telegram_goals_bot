from __future__ import annotations

import pytest

from app.sheets.gateway import GoogleSheetsError, _execute


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status


class _HttpFailure(Exception):
    def __init__(
        self,
        status: int,
        message: str = "provider detail",
        *,
        reason: str | None = None,
    ) -> None:
        super().__init__(message)
        self.resp = _Response(status)
        self.error_details = [{"reason": reason}] if reason else []


class _SequenceRequest:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def execute(self) -> dict[str, object]:
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, dict)
        return outcome


def test_execute_recovers_after_temporary_google_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _SequenceRequest([_HttpFailure(503), TimeoutError(), {"values": [["ok"]]}])
    delays: list[float] = []
    monkeypatch.setattr("app.sheets.gateway.sleep", delays.append)

    result = _execute(request, retry_safe=True)

    assert result == {"values": [["ok"]]}
    assert request.calls == 3
    assert delays == [0.25, 0.5]


def test_execute_does_not_retry_permanent_google_permission_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _SequenceRequest([_HttpFailure(403, "private provider detail")])
    delays: list[float] = []
    monkeypatch.setattr("app.sheets.gateway.sleep", delays.append)

    with pytest.raises(GoogleSheetsError) as error:
        _execute(request, retry_safe=True)

    assert request.calls == 1
    assert delays == []
    assert "private provider detail" not in str(error.value)


def test_execute_stops_after_bounded_temporary_failure_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _SequenceRequest([_HttpFailure(429), _HttpFailure(429), _HttpFailure(429)])
    delays: list[float] = []
    monkeypatch.setattr("app.sheets.gateway.sleep", delays.append)

    with pytest.raises(GoogleSheetsError):
        _execute(request, retry_safe=True)

    assert request.calls == 3
    assert delays == [0.25, 0.5]


def test_execute_retries_google_403_rate_limit_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _SequenceRequest(
        [_HttpFailure(403, reason="userRateLimitExceeded"), {"values": [["ok"]]}]
    )
    delays: list[float] = []
    monkeypatch.setattr("app.sheets.gateway.sleep", delays.append)

    assert _execute(request, retry_safe=True) == {"values": [["ok"]]}
    assert request.calls == 2
    assert delays == [0.25]


def test_execute_does_not_retry_non_idempotent_append_after_transport_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _SequenceRequest([TimeoutError(), {"updates": {"updatedRows": 1}}])
    delays: list[float] = []
    monkeypatch.setattr("app.sheets.gateway.sleep", delays.append)

    with pytest.raises(GoogleSheetsError):
        _execute(request)

    assert request.calls == 1
    assert delays == []
