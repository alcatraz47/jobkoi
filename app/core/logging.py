"""Logging setup utilities."""

from __future__ import annotations

import logging

LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging for the application.

    Args:
        level: Minimum log level for emitted records.
    """

    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, force=True)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance.

    Args:
        name: Logger namespace.

    Returns:
        Logger instance bound to the provided namespace.
    """

    return logging.getLogger(name)
