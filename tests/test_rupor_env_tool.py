import json
from pathlib import Path
import stat

import pytest

from scripts.upsert_rupor_env import upsert_rupor_env


def test_upsert_rupor_env_preserves_unrelated_lines_and_replaces_duplicates(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "# existing\nMAIN=value\nRUPOR_TELEGRAM_BOT_TOKEN=old\n"
        "RUPOR_TELEGRAM_BOT_TOKEN=duplicate\nRUPOR_ALLOWED_TELEGRAM_IDS=1,2,3",
        encoding="utf-8",
    )
    config_path = tmp_path / "rupor.json"
    config_path.write_text(
        json.dumps({"token": "123456:ABC_def-789", "allowed_ids": "101,102,103"}),
        encoding="utf-8",
    )

    upsert_rupor_env(env_path, config_path)

    text = env_path.read_text(encoding="utf-8")
    assert text == (
        "# existing\nMAIN=value\nRUPOR_TELEGRAM_BOT_TOKEN=123456:ABC_def-789\n"
        "RUPOR_ALLOWED_TELEGRAM_IDS=101,102,103\n"
    )
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600


@pytest.mark.parametrize(
    "payload",
    [
        {"token": "bad token", "allowed_ids": "101,102,103"},
        {"token": "123:ABC", "allowed_ids": "101,101,103"},
        {"token": "123:ABC", "allowed_ids": "101,102"},
    ],
)
def test_upsert_rupor_env_rejects_invalid_protected_config(
    tmp_path: Path, payload: dict[str, str]
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("MAIN=value\n", encoding="utf-8")
    config_path = tmp_path / "rupor.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError):
        upsert_rupor_env(env_path, config_path)

    assert env_path.read_text(encoding="utf-8") == "MAIN=value\n"
