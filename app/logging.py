"""Logging setup for the application foundation."""

from __future__ import annotations

import logging

from app.config import Settings, redact_mapping


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure and return the application logger."""

    logger = logging.getLogger("telegram_goals_bot")
    logger.setLevel(settings.runtime.log_level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
        logger.addHandler(handler)

    logger.propagate = True
    logger.debug("settings loaded", extra={"settings": redact_mapping(settings.as_dict())})
    return logger
