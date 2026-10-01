"""Run one Secret Santa program from config through delivery."""

import logging
from pathlib import Path

from secret_santa.config import ProgramConfig
from secret_santa.emailer import AssignmentMailer
from secret_santa.exceptions import SecretSantaError
from secret_santa.logging_config import setup_logging
from secret_santa.models import SolveResult
from secret_santa.registry import RegistryLoader
from secret_santa.report import ProgramReporter, checks_summary
from secret_santa.solver import ExchangeSolver

logger = logging.getLogger("secret_santa.program")


class SecretSantaProgram:
    """Orchestrate loading, solving, organizer logging, and email delivery."""

    def __init__(self, config: ProgramConfig) -> None:
        """Bind a program to an already validated config.

        Args:
            config: Program hyperparameters.
        """
        self._config = config

    @classmethod
    def from_config_file(cls, path: str | Path) -> "SecretSantaProgram":
        """Load config and configure logging.

        Args:
            path: YAML config path.

        Returns:
            A program ready to run.
        """
        config = ProgramConfig.load(path)
        setup_logging(config.log_level)
        return cls(config)

    def run(self) -> SolveResult:
        """Solve the exchange, log every pairing, then email each giver.

        The organizer report is written for both mock and live email modes, and
        it is written before any message is sent. Email is skipped when the
        assignment fails its own invariant checks.

        Returns:
            The solved assignment.

        Raises:
            SecretSantaError: The registry, solver, validation, or mailer failed.
        """
        logger.info("Loading registry from %s", self._config.registry_path)
        registry = RegistryLoader().load(self._config.registry_path)
        logger.info("Solving assignment for %d participants", len(registry.participants))
        result = ExchangeSolver(seed=self._config.seed).solve(registry)
        ProgramReporter().log(result, self._config)
        if not result.checks.passed():
            raise SecretSantaError(
                "Assignment failed validation; no emails were sent. "
                f"{checks_summary(result.checks)}"
            )
        AssignmentMailer(self._config).deliver(result)
        logger.info("Finished Secret Santa program for %d assignments", len(result.assignments))
        return result


def run_program(config_path: str | Path) -> SolveResult:
    """Load ``config_path``, solve the exchange, log it, and email assignments.

    Args:
        config_path: YAML config path.

    Returns:
        The solved assignment.
    """
    return SecretSantaProgram.from_config_file(config_path).run()
