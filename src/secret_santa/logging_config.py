"""Logging setup for organizer output."""

import logging

from secret_santa.exceptions import ConfigValidationError

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str) -> None:
    """Configure the ``secret_santa`` logger.

    Replaces any previous package handlers so repeated runs do not duplicate lines.
    Records still propagate to the root logger so tests can capture them.

    Args:
        level: Level name such as ``INFO`` or ``DEBUG``.

    Raises:
        ConfigValidationError: ``level`` is not a known logging level.
    """
    numeric_level: int | None = logging.getLevelNamesMapping().get(level.upper())
    if numeric_level is None:
        raise ConfigValidationError(f"Unknown log level: {level}")

    package_logger = logging.getLogger("secret_santa")
    package_logger.setLevel(numeric_level)
    package_logger.propagate = True
    package_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    package_logger.addHandler(handler)
