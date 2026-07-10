"""Production runtime readiness helpers and CLI commands."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from pathlib import Path
from typing import Sequence

from app.config import ConfigurationError, Settings, load_settings
from app.logging import setup_logging
from app.bot.dispatch import TelegramUpdate, TelegramUpdateDispatcher, parse_telegram_update
from app.storage.sqlite import REQUIRED_TECHNICAL_TABLES, initialize_schema, list_tables


class RuntimeNotImplementedError(RuntimeError):
    """Raised until the live Telegram polling runtime exists."""


@dataclass(frozen=True)
class RuntimeInitializationResult:
    sqlite_db_path: Path
    created_storage_dirs: tuple[Path, ...]
    technical_tables: frozenset[str]


def initialize_runtime(settings: Settings) -> RuntimeInitializationResult:
    """Prepare local technical storage for the production runtime."""

    storage_dirs = (
        settings.storage.sqlite_db_path.parent,
        settings.storage.audio_storage_dir,
        settings.storage.pdf_storage_dir,
    )
    for directory in storage_dirs:
        directory.mkdir(parents=True, exist_ok=True)

    initialize_schema(settings.storage.sqlite_db_path)
    tables = frozenset(list_tables(settings.storage.sqlite_db_path))
    missing_tables = REQUIRED_TECHNICAL_TABLES - tables
    if missing_tables:
        missing_text = ", ".join(sorted(missing_tables))
        raise ConfigurationError(f"SQLite schema initialization incomplete: {missing_text}")

    return RuntimeInitializationResult(
        sqlite_db_path=settings.storage.sqlite_db_path,
        created_storage_dirs=storage_dirs,
        technical_tables=tables,
    )


def run_bot(settings: Settings) -> None:
    """Run the live bot process once Telegram/Google adapters are implemented."""

    initialize_runtime(settings)
    raise RuntimeNotImplementedError(
        "live Telegram polling runtime is not implemented; implement live adapters before service start"
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="telegram-goals-bot")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to environment file. Use an empty string to disable file loading.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-config", help="Load config and initialize technical storage.")
    subparsers.add_parser("init-storage", help="Create local storage directories and SQLite schema.")
    subparsers.add_parser("run", help="Start live bot runtime after adapters are implemented.")

    args = parser.parse_args(list(argv) if argv is not None else None)
    env_file = None if args.env_file == "" else args.env_file

    try:
        settings = load_settings(env_file=env_file, strict=True)
        logger = setup_logging(settings)
        result = initialize_runtime(settings)
        logger.info("runtime storage ready", extra={"sqlite_db_path": str(result.sqlite_db_path)})

        if args.command in {"check-config", "init-storage"}:
            return 0
        if args.command == "run":
            run_bot(settings)
            return 0
    except RuntimeNotImplementedError as exc:
        print(str(exc), file=sys.stderr)
        return 78
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 2
