from pathlib import Path

from app.storage.registration import RegistrationDraft, RegistrationDraftRepository
from app.storage.sqlite import initialize_schema


def test_registration_finalization_claim_is_atomic(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = RegistrationDraftRepository(db_path)
    repository.save(
        RegistrationDraft(
            telegram_id=404,
            flow_id="FLOW_2",
            consent_given_at="2026-09-10T10:00:00+05:00",
            created_at="2026-09-10T10:00:00+05:00",
            updated_at="2026-09-10T10:00:00+05:00",
            expires_at="2026-09-16T18:00:00+05:00",
        )
    )

    assert repository.claim_finalization(
        404,
        claim_token="worker-a",
        updated_at="2026-09-10T10:01:00+05:00",
        stale_before="2026-09-10T09:51:00+05:00",
    ) is True
    assert repository.claim_finalization(
        404,
        claim_token="worker-b",
        updated_at="2026-09-10T10:01:01+05:00",
        stale_before="2026-09-10T09:51:01+05:00",
    ) is False
    assert repository.get(404).status == "finalizing"
    repository.release_finalization(404, claim_token="worker-b", updated_at="2026-09-10T10:02:00+05:00")
    assert repository.get(404).status == "finalizing"
    repository.release_finalization(404, claim_token="worker-a", updated_at="2026-09-10T10:02:01+05:00")
    assert repository.get(404).status == "active"


def test_only_current_claim_owner_can_complete_registration(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = RegistrationDraftRepository(db_path)
    repository.save(
        RegistrationDraft(
            telegram_id=404,
            flow_id="FLOW_2",
            created_at="2026-09-10T10:00:00+05:00",
            updated_at="2026-09-10T10:00:00+05:00",
            expires_at="2026-09-16T18:00:00+05:00",
        )
    )
    assert repository.claim_finalization(
        404,
        claim_token="current-worker",
        updated_at="2026-09-10T10:01:00+05:00",
        stale_before="2026-09-10T09:00:00+05:00",
    )

    assert not repository.owns_finalization(404, claim_token="stale-worker")
    assert not repository.complete_finalization(404, claim_token="stale-worker")
    assert repository.get(404) is not None
    assert repository.owns_finalization(404, claim_token="current-worker")
    assert repository.complete_finalization(404, claim_token="current-worker")
    assert repository.get(404) is None


def test_stale_worker_cannot_release_or_complete_after_claim_takeover(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite3"
    initialize_schema(db_path)
    repository = RegistrationDraftRepository(db_path)
    repository.save(
        RegistrationDraft(
            telegram_id=404,
            flow_id="FLOW_2",
            created_at="2026-09-10T10:00:00+05:00",
            updated_at="2026-09-10T10:00:00+05:00",
            expires_at="2026-09-16T18:00:00+05:00",
        )
    )
    assert repository.claim_finalization(
        404, claim_token="worker-a", updated_at="2026-09-10T10:01:00+05:00",
        stale_before="2026-09-10T09:00:00+05:00",
    )
    assert repository.claim_finalization(
        404, claim_token="worker-b", updated_at="2026-09-10T10:12:00+05:00",
        stale_before="2026-09-10T10:02:00+05:00",
    )

    repository.release_finalization(
        404, claim_token="worker-a", updated_at="2026-09-10T10:12:01+05:00"
    )
    assert not repository.complete_finalization(404, claim_token="worker-a")
    current = repository.get(404)
    assert current is not None
    assert (current.status, current.claim_token) == ("finalizing", "worker-b")
    assert repository.complete_finalization(404, claim_token="worker-b")
