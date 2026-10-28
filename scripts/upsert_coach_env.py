#!/usr/bin/env python3
"""Apply an explicitly configured global report recipient without exposing env contents."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile


def upsert_coach_env(env_path: Path, config_path: Path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    telegram_id = payload.get("sitnikov_telegram_id") if isinstance(payload, dict) else None
    if not isinstance(telegram_id, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", telegram_id):
        raise ValueError("Invalid coach Telegram ID")
    original = env_path.read_text(encoding="utf-8")
    metadata = env_path.stat()
    key = "SITNIKOV_TELEGRAM_ID"
    replacement = f"{key}={telegram_id}"
    result: list[str] = []
    seen = False
    for line in original.splitlines():
        name = line.split("=", 1)[0].strip() if "=" in line else ""
        if name == key:
            if not seen:
                result.append(replacement)
                seen = True
        else:
            result.append(line)
    if not seen:
        result.append(replacement)
    # Replace atomically in the same directory while preserving the existing owner.
    fd, temporary = tempfile.mkstemp(prefix=".coach-env-", dir=env_path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
            stream.write("\n".join(result) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, env_path)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: upsert_coach_env.py ENV_PATH CONFIG_PATH")
    upsert_coach_env(Path(sys.argv[1]), Path(sys.argv[2]))
