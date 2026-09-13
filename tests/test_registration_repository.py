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
