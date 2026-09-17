from __future__ import annotations

from threading import Event, Thread

import pytest

from app.sheets.gateway import GoogleSheetsError, _execute, _GOOGLE_REQUEST_LOCK


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


def test_execute_serializes_requests_for_shared_google_client() -> None:
    first_entered = Event()
    release_first = Event()
    execution_order: list[str] = []

    class BlockingRequest:
        def __init__(self, name: str) -> None:
            self.name = name

        def execute(self) -> dict[str, object]:
            execution_order.append(f"{self.name}:start")
            if self.name == "first":
                first_entered.set()
                assert release_first.wait(timeout=2)
            execution_order.append(f"{self.name}:end")
            return {"name": self.name}

    first = Thread(target=_execute, args=(BlockingRequest("first"),))
    first.start()
    assert first_entered.wait(timeout=2)
    assert not _GOOGLE_REQUEST_LOCK.acquire(blocking=False)
    release_first.set()
    first.join(timeout=2)
    assert not first.is_alive()

    second = Thread(target=_execute, args=(BlockingRequest("second"),))
    second.start()
    second.join(timeout=2)

    assert execution_order == ["first:start", "first:end", "second:start", "second:end"]


def test_execute_releases_shared_lock_after_request_failure() -> None:
    class FailingRequest:
        def execute(self) -> dict[str, object]:
            raise RuntimeError("boom")

    with pytest.raises(GoogleSheetsError):
        _execute(FailingRequest())

    result: list[dict[str, object]] = []
    thread = Thread(target=lambda: result.append(_execute(_SequenceRequest([{"ok": True}]))))
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert result == [{"ok": True}]
