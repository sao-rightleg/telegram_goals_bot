import json
from pathlib import Path

import pytest

from scripts.upsert_coach_env import upsert_coach_env


def test_updates_only_coach_and_preserves_permissions(tmp_path: Path) -> None:
    env = tmp_path / '.env'
    env.write_text('# config\nTOKEN=private\nSITNIKOV_TELEGRAM_ID=1\nSITNIKOV_TELEGRAM_ID=2\n')
    env.chmod(0o600)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'sitnikov_telegram_id': '429360776'}))
    upsert_coach_env(env, config)
    assert env.read_text() == '# config\nTOKEN=private\nSITNIKOV_TELEGRAM_ID=429360776\n'
    assert env.stat().st_mode & 0o777 == 0o600
    upsert_coach_env(env, config)
    assert env.read_text().count('SITNIKOV_TELEGRAM_ID=') == 1


@pytest.mark.parametrize('value', ['', '0', '-1', '12\nTOKEN=bad', '$(id)', '1 2', 123, None])
def test_invalid_id_leaves_config_unchanged(tmp_path: Path, value: object) -> None:
    env = tmp_path / '.env'
    original = 'SITNIKOV_TELEGRAM_ID=1\n'
    env.write_text(original)
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'sitnikov_telegram_id': value}))
    with pytest.raises(ValueError, match='Invalid coach Telegram ID'):
        upsert_coach_env(env, config)
    assert env.read_text() == original


def test_appends_missing_setting(tmp_path: Path) -> None:
    env = tmp_path / '.env'
    env.write_text('TOKEN=private\n')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'sitnikov_telegram_id': '429360776'}))
    upsert_coach_env(env, config)
    assert env.read_text() == 'TOKEN=private\nSITNIKOV_TELEGRAM_ID=429360776\n'


def test_failed_atomic_replace_preserves_original_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    env = tmp_path / '.env'
    env.write_text('SITNIKOV_TELEGRAM_ID=1\n')
    config = tmp_path / 'config.json'
    config.write_text(json.dumps({'sitnikov_telegram_id': '429360776'}))

    def fail_replace(*args: object) -> None:
        raise OSError('replace failed')

    monkeypatch.setattr('scripts.upsert_coach_env.os.replace', fail_replace)
    with pytest.raises(OSError, match='replace failed'):
        upsert_coach_env(env, config)
    assert env.read_text() == 'SITNIKOV_TELEGRAM_ID=1\n'
    assert not list(tmp_path.glob('.coach-env-*'))
