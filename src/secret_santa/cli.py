"""Command-line entry point."""

import argparse
import logging
from pathlib import Path

from secret_santa.exceptions import SecretSantaError
from secret_santa.logging_config import setup_logging
from secret_santa.program import run_program

logger = logging.getLogger("secret_santa.cli")


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the Secret Santa command."""
    parser = argparse.ArgumentParser(
        description="Solve a multi-family Secret Santa program and email each giver.",
    )
    parser.add_argument(
        "--config",
        required=True,
        type=Path,
        help="Path to the YAML program config.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the program and return a process status code.

    Args:
        argv: Arguments excluding the program name. Defaults to ``sys.argv``.

    Returns:
        ``0`` after a solved program is logged and emailed, ``1`` on a known failure.
    """
    setup_logging("INFO")
    args = build_parser().parse_args(argv)
    try:
        run_program(args.config)
    except SecretSantaError as exc:
        logger.error("%s", exc)
        return 1
    return 0
