"""Constrained Secret Santa matching."""

import logging
import random
from collections.abc import Mapping, Sequence

from secret_santa.exceptions import InfeasibleProgramError
from secret_santa.models import (
    Assignment,
    AssignmentChecks,
    Participant,
    Registry,
    RemovedParticipant,
    SolveResult,
)

logger = logging.getLogger("secret_santa.solver")


class ExchangeSolver:
    """Find a random one-to-one assignment that respects exclusions.

    The allowed graph is symmetric: if A excludes B, or excludes B's group, then
    neither A nor B may give to the other. Self-assignment is never allowed.
    Participants with no legal giver or recipient are removed. If the remaining
    graph has no perfect matching, the program is infeasible.
    """

    def __init__(self, seed: int | None = None) -> None:
        """Create a solver.

        Args:
            seed: Optional seed for the random matching search.
        """
        self._rng = random.Random(seed)

    def solve(self, registry: Registry) -> SolveResult:
        """Assign each remaining participant one recipient.

        Args:
            registry: Cleaned participants and ignored exclusion tokens.

        Returns:
            Pairings plus pruning and validation metadata.

        Raises:
            InfeasibleProgramError: Fewer than two participants remain, or no
                complete assignment exists.
        """
        participants = registry.participants
        allowed = self._allowed_graph(participants)
        pruned, removed = self._prune(allowed)
        if len(pruned) < 2:
            raise InfeasibleProgramError(
                f"Only {len(pruned)} participant(s) remain after removing "
                f"{len(removed)} infeasible participant(s); at least 2 are required."
            )

        pairing = self._perfect_matching(pruned)
        if pairing is None:
            raise InfeasibleProgramError(
                "No complete Secret Santa assignment exists for "
                f"{len(pruned)} participants after removing {len(removed)} "
                "infeasible participant(s)."
            )

        by_name = {participant.name: participant for participant in participants}
        assignments = tuple(
            Assignment(giver=by_name[giver], recipient=by_name[recipient])
            for giver, recipient in sorted(pairing.items())
        )
        checks = self._checks(assignments, participants, removed)
        return SolveResult(
            assignments=assignments,
            loaded_count=len(participants),
            removed=tuple(removed),
            ignored_exclusions=registry.ignored_exclusions,
            checks=checks,
        )

    def _allowed_graph(self, participants: Sequence[Participant]) -> dict[str, set[str]]:
        """Return giver name to the set of legal recipient names.

        Exclusion edges are closed symmetrically here, including exclusions that
        were declared by only one of the two people.
        """
        names = {participant.name for participant in participants}
        forbidden: dict[str, set[str]] = {name: set() for name in names}
        for participant in participants:
            for other in participant.excluded_names:
                if other not in names:
                    continue
                forbidden[participant.name].add(other)
                forbidden[other].add(participant.name)

        allowed: dict[str, set[str]] = {}
        for name in names:
            allowed[name] = {
                other
                for other in names
                if other != name and other not in forbidden[name]
            }
        return allowed

    def _prune(self, allowed: Mapping[str, set[str]]) -> tuple[dict[str, set[str]], list[RemovedParticipant]]:
        """Drop participants who have no legal recipient or no legal giver.

        Removing a person can only reduce other degrees, so the scan repeats until
        every remaining person has an incoming and an outgoing edge. People who
        still cannot form a perfect matching are left for the matcher to reject.
        """
        graph: dict[str, set[str]] = {name: set(recipients) for name, recipients in allowed.items()}
        removed: list[RemovedParticipant] = []
        while True:
            incoming = {name: 0 for name in graph}
            for recipients in graph.values():
                for recipient in recipients:
                    incoming[recipient] = incoming.get(recipient, 0) + 1

            victims: list[RemovedParticipant] = []
            for name in sorted(graph):
                out_degree = len(graph[name])
                in_degree = incoming.get(name, 0)
                if out_degree > 0 and in_degree > 0:
                    continue
                if out_degree == 0 and in_degree == 0:
                    reason = "no legal giver or recipient"
                elif out_degree == 0:
                    reason = "no legal recipient"
                else:
                    reason = "no legal giver"
                victims.append(RemovedParticipant(name, reason))

            if not victims:
                return graph, removed

            victim_names = {victim.name for victim in victims}
            for victim in victims:
                logger.warning("Removed infeasible participant %s: %s", victim.name, victim.reason)
                removed.append(victim)
                del graph[victim.name]
            for name in graph:
                graph[name] -= victim_names

    def _perfect_matching(self, allowed: Mapping[str, set[str]]) -> dict[str, str] | None:
        """Return one giver-to-recipient map, or ``None`` when none exists.

        Edge order is shuffled so successive runs can produce different valid
        assignments. The search itself is augmenting-path matching, so a perfect
        matching is found whenever one exists.
        """
        adjacency: dict[str, list[str]] = {}
        givers = list(allowed)
        self._rng.shuffle(givers)
        for giver, recipients in allowed.items():
            ordered = list(recipients)
            self._rng.shuffle(ordered)
            adjacency[giver] = ordered

        recipient_to_giver: dict[str, str] = {}

        def find_augmenting_path(giver: str, seen: set[str]) -> bool:
            """Assign ``giver`` by augmenting the current matching."""
            for recipient in adjacency[giver]:
                if recipient in seen:
                    continue
                seen.add(recipient)
                current_giver = recipient_to_giver.get(recipient)
                if current_giver is None or find_augmenting_path(current_giver, seen):
                    recipient_to_giver[recipient] = giver
                    return True
            return False

        for giver in givers:
            if not find_augmenting_path(giver, set()):
                return None
        return {giver: recipient for recipient, giver in recipient_to_giver.items()}

    def _checks(
        self,
        assignments: Sequence[Assignment],
        participants: Sequence[Participant],
        removed: Sequence[RemovedParticipant],
    ) -> AssignmentChecks:
        """Evaluate permutation, self-assignment, and exclusion invariants."""
        removed_names = {participant.name for participant in removed}
        active_names = {participant.name for participant in participants if participant.name not in removed_names}
        givers = [assignment.giver.name for assignment in assignments]
        recipients = [assignment.recipient.name for assignment in assignments]
        is_permutation = (
            len(assignments) == len(active_names)
            and set(givers) == active_names
            and set(recipients) == active_names
            and len(set(givers)) == len(givers)
        )
        no_self_assignments = all(
            assignment.giver.name != assignment.recipient.name for assignment in assignments
        )
        exclusions_respected = all(
            assignment.recipient.name not in assignment.giver.excluded_names
            and assignment.giver.name not in assignment.recipient.excluded_names
            for assignment in assignments
        )
        return AssignmentChecks(
            is_permutation=is_permutation,
            no_self_assignments=no_self_assignments,
            exclusions_respected=exclusions_respected,
        )
