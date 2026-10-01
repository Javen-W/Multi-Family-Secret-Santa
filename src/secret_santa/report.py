"""Organizer log for a solved Secret Santa program."""

import logging

from secret_santa.config import ProgramConfig
from secret_santa.models import AssignmentChecks, IgnoredExclusion, RemovedParticipant, SolveResult

logger = logging.getLogger("secret_santa.report")

_RULE_WIDTH = 64


class ProgramReporter:
    """Format and log the organizer record of a solved program.

    The report is written at INFO for both mock and live email modes. It is the
    only place the full pairing list is recorded. Participant emails stay limited
    to one recipient.
    """

    def log(self, result: SolveResult, config: ProgramConfig) -> str:
        """Log the program report and return the same text.

        Args:
            result: Solved assignment and validation metadata.
            config: Program settings used for the metadata section.

        Returns:
            The formatted report, without logging prefixes.
        """
        text = self.format(result, config)
        for line in text.splitlines():
            logger.info("%s", line)
        return text

    def format(self, result: SolveResult, config: ProgramConfig) -> str:
        """Build the multi-line organizer report.

        Args:
            result: Solved assignment and validation metadata.
            config: Program settings used for the metadata section.

        Returns:
            A stable, human-readable report.
        """
        seed_label = "none" if config.seed is None else str(config.seed)
        ordered_assignments = sorted(result.assignments, key=lambda item: item.giver.name)
        lines: list[str] = [
            "Secret Santa program",
            "=" * _RULE_WIDTH,
            _field("Registry:", str(config.registry_path)),
            _field("Price limit:", config.price_label()),
            _field("Email mode:", config.email_mode()),
            _field("Random seed:", seed_label),
            _field("Participants loaded:", str(result.loaded_count)),
            _field("Participants removed:", str(len(result.removed))),
            _field("Participants assigned:", str(len(result.assignments))),
            "",
            "Validation",
            "-" * _RULE_WIDTH,
            "Ignored exclusion tokens:",
            *_bullet_lines(_ignored_lines(result.ignored_exclusions)),
            "Removed participants:",
            *_bullet_lines(_removed_lines(result.removed)),
            _field("Permutation:", _mark(result.checks.is_permutation)),
            _field("No self-assignments:", _mark(result.checks.no_self_assignments)),
            _field("Exclusions respected:", _mark(result.checks.exclusions_respected)),
            "",
            "Assignments",
            "-" * _RULE_WIDTH,
        ]
        for assignment in ordered_assignments:
            giver = assignment.giver
            recipient = assignment.recipient
            lines.append(
                f"{giver.name} ({giver.group_label()}) -> {recipient.name} ({recipient.group_label()})"
            )
        lines.append("=" * _RULE_WIDTH)
        return "\n".join(lines)


def _field(label: str, value: str) -> str:
    """Align a metadata label with its value."""
    return f"{label:<24}{value}"


def _mark(passed: bool) -> str:
    """Return the validation word shown in the report."""
    if passed:
        return "ok"
    return "failed"


def _bullet_lines(items: list[str]) -> list[str]:
    """Return indented items, or a single ``(none)`` placeholder."""
    if not items:
        return ["  (none)"]
    return [f"  {item}" for item in items]


def _ignored_lines(ignored: tuple[IgnoredExclusion, ...]) -> list[str]:
    """Sort ignored tokens for a stable report."""
    ordered = sorted(ignored, key=lambda item: (item.participant, item.token, item.reason))
    return [f"{item.participant}: {item.token} ({item.reason})" for item in ordered]


def _removed_lines(removed: tuple[RemovedParticipant, ...]) -> list[str]:
    """Sort removed participants for a stable report."""
    ordered = sorted(removed, key=lambda item: item.name)
    return [f"{item.name}: {item.reason}" for item in ordered]


def checks_summary(checks: AssignmentChecks) -> str:
    """Return a one-line summary used when validation fails before email."""
    return (
        "permutation="
        f"{_mark(checks.is_permutation)}, "
        f"no_self_assignments={_mark(checks.no_self_assignments)}, "
        f"exclusions_respected={_mark(checks.exclusions_respected)}"
    )
