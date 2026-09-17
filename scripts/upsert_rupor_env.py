#!/usr/bin/env python3
"""Upsert optional RUPOR settings from a protected JSON file into a protected env file."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys


TOKEN_PATTERN = re.compile(r"^[0-9]+:[A-Za-z0-9_-]+$")
IDS_PATTERN = re.compile(r"^[1-9][0-9]*,[1-9][0-9]*,[1-9][0-9]*$")


def upsert_rupor_env(env_path: Path, config_path: Path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    token = payload.get("token")
    allowed_ids = payload.get("allowed_ids")
    if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("invalid RUPOR bot token")
    if not isinstance(allowed_ids, str) or not IDS_PATTERN.fullmatch(allowed_ids):
        raise ValueError("invalid RUPOR allowed IDs")
    if len(set(allowed_ids.split(","))) != 3:
        raise ValueError("RUPOR allowed IDs must be unique")
    updates = {
        "RUPOR_TELEGRAM_BOT_TOKEN": token,
        "RUPOR_ALLOWED_TELEGRAM_IDS": allowed_ids,
    }
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in updates:
            if key not in seen:
                result.append(f"{key}={updates[key]}")
                seen.add(key)
        else:
            result.append(line)
    result.extend(f"{key}={value}" for key, value in updates.items() if key not in seen)
    env_path.write_text("\n".join(result) + "\n", encoding="utf-8")
    env_path.chmod(0o600)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: upsert_rupor_env.py ENV_PATH CONFIG_PATH", file=sys.stderr)
        return 2
    upsert_rupor_env(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
