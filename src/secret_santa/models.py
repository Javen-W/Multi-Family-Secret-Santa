"""Domain types for participants, registries, and solved programs."""

from dataclasses import dataclass
from pathlib import Path


def is_valid_email(address: str) -> bool:
    """Return whether ``address`` looks like a usable email address.

    Args:
        address: Candidate address after surrounding whitespace has been removed.

    Returns:
        True when the address has one ``@``, non-empty local and domain parts,
        and no spaces.
    """
    if not address or any(character.isspace() for character in address):
        return False
    local, separator, domain = address.partition("@")
    if separator != "@" or not local or not domain or "@" in domain:
        return False
    return "." in domain


@dataclass(frozen=True)
class IgnoredExclusion:
    """An exclusion token that did not remove any other participant.

    Attributes:
        participant: Registry name that declared the token.
        token: Token text after cleaning.
        reason: ``unknown`` when nothing matched, or ``self`` for a self reference.
    """

    participant: str
    token: str
    reason: str


@dataclass(frozen=True)
class Participant:
    """One person registered for a gift exchange.

    Attributes:
        name: Unique participant identifier.
        email: Address that receives this person's assignment.
        group: Optional social-circle label. Sharing a group does not block pairing.
        exclusion_tokens: Cleaned tokens from the registry, in first-seen order.
        excluded_names: Other participants named directly by those tokens.
    """

    name: str
    email: str
    group: str | None
    exclusion_tokens: tuple[str, ...]
    excluded_names: frozenset[str]

    def group_label(self) -> str:
        """Return the group name, or ``none`` when the participant has no group."""
        if self.group:
            return self.group
        return "none"


@dataclass(frozen=True)
class Registry:
    """Participants loaded from one CSV file.

    Attributes:
        path: Resolved path of the file that was read.
        participants: Cleaned participants in file order.
        ignored_exclusions: Tokens skipped while resolving exclusions.
    """

    path: Path
    participants: tuple[Participant, ...]
    ignored_exclusions: tuple[IgnoredExclusion, ...]


@dataclass(frozen=True)
class RemovedParticipant:
    """A participant dropped because they had no legal giver or recipient.

    Attributes:
        name: Participant name.
        reason: Why the participant could not stay in the program.
    """

    name: str
    reason: str


@dataclass(frozen=True)
class Assignment:
    """One giver paired with the recipient of their gift.

    Attributes:
        giver: Participant who gives the gift.
        recipient: Participant who receives that gift.
    """

    giver: Participant
    recipient: Participant


@dataclass(frozen=True)
class AssignmentChecks:
    """Invariant checks for a finished assignment.

    Attributes:
        is_permutation: Every active participant is one giver and one recipient.
        no_self_assignments: Nobody is paired with themselves.
        exclusions_respected: No forbidden pair appears in either direction.
    """

    is_permutation: bool
    no_self_assignments: bool
    exclusions_respected: bool

    def passed(self) -> bool:
        """Return whether every invariant holds."""
        return self.is_permutation and self.no_self_assignments and self.exclusions_respected


@dataclass(frozen=True)
class SolveResult:
    """A solved exchange, including cleaning and validation metadata.

    Attributes:
        assignments: Pairings for participants who remained in the program.
        loaded_count: Participants present in the registry before pruning.
        removed: Participants dropped because they had no legal partner.
        ignored_exclusions: Exclusion tokens that did not match another person.
        checks: Invariant results for ``assignments``.
    """

    assignments: tuple[Assignment, ...]
    loaded_count: int
    removed: tuple[RemovedParticipant, ...]
    ignored_exclusions: tuple[IgnoredExclusion, ...]
    checks: AssignmentChecks
