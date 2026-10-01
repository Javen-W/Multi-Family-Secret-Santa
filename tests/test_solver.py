"""Matching invariants, pruning, and infeasible programs."""

from pathlib import Path

import pytest

from secret_santa.exceptions import InfeasibleProgramError
from secret_santa.models import Participant, Registry, SolveResult
from secret_santa.registry import RegistryLoader
from secret_santa.solver import ExchangeSolver


def _person(
    name: str,
    *,
    group: str | None = None,
    excluded: tuple[str, ...] = (),
) -> Participant:
    return Participant(
        name=name,
        email=f"{name.lower()}@example.com",
        group=group,
        exclusion_tokens=excluded,
        excluded_names=frozenset(excluded),
    )


def _registry(*participants: Participant) -> Registry:
    return Registry(
        path=Path("memory.csv"),
        participants=participants,
        ignored_exclusions=(),
    )


def _assert_invariants(result: SolveResult) -> None:
    assignments = result.assignments
    removed = {item.name for item in result.removed}
    givers = [assignment.giver.name for assignment in assignments]
    recipients = [assignment.recipient.name for assignment in assignments]
    assert result.checks.passed()
    assert sorted(givers) == sorted(recipients)
    assert len(givers) == len(set(givers))
    assert removed.isdisjoint(givers)
    for assignment in assignments:
        assert assignment.giver.name != assignment.recipient.name
        assert assignment.recipient.name not in assignment.giver.excluded_names
        assert assignment.giver.name not in assignment.recipient.excluded_names


def test_same_group_can_be_paired() -> None:
    result = ExchangeSolver(seed=0).solve(
        _registry(_person("Ann", group="A"), _person("Bob", group="A"))
    )

    pairs = {(assignment.giver.name, assignment.recipient.name) for assignment in result.assignments}
    assert pairs == {("Ann", "Bob"), ("Bob", "Ann")}
    _assert_invariants(result)


def test_one_sided_exclusion_blocks_both_directions() -> None:
    participants = (
        _person("Ann", excluded=("Bob",)),
        _person("Bob"),
        _person("Cara"),
        _person("Dan"),
    )
    for seed in range(8):
        result = ExchangeSolver(seed=seed).solve(_registry(*participants))
        _assert_invariants(result)
        for assignment in result.assignments:
            pair = {assignment.giver.name, assignment.recipient.name}
            assert pair != {"Ann", "Bob"}


def test_allowed_graph_is_symmetric() -> None:
    participants = (
        _person("Ann", excluded=("Bob",)),
        _person("Bob"),
        _person("Cara", excluded=("Dan",)),
        _person("Dan"),
    )
    allowed = ExchangeSolver(seed=0)._allowed_graph(participants)

    for giver, recipients in allowed.items():
        assert giver not in recipients
        for recipient in recipients:
            assert giver in allowed[recipient]


def test_degree_zero_giver_is_removed_and_the_rest_are_matched() -> None:
    result = ExchangeSolver(seed=2).solve(
        _registry(
            _person("Ann"),
            _person("Bob"),
            _person("Cara"),
            _person("Zoe", excluded=("Ann", "Bob", "Cara")),
        )
    )

    assert [(item.name, item.reason) for item in result.removed] == [
        ("Zoe", "no legal giver or recipient")
    ]
    assert {assignment.giver.name for assignment in result.assignments} == {"Ann", "Bob", "Cara"}
    _assert_invariants(result)


def test_person_excluded_by_everyone_is_removed() -> None:
    result = ExchangeSolver(seed=2).solve(
        _registry(
            _person("Ann", excluded=("Zoe",)),
            _person("Bob", excluded=("Zoe",)),
            _person("Cara", excluded=("Zoe",)),
            _person("Zoe"),
        )
    )

    assert [(item.name, item.reason) for item in result.removed] == [
        ("Zoe", "no legal giver or recipient")
    ]
    _assert_invariants(result)


def test_path_of_three_is_infeasible_without_dropping_degree_positive_people() -> None:
    with pytest.raises(InfeasibleProgramError, match="No complete Secret Santa assignment"):
        ExchangeSolver(seed=0).solve(
            _registry(
                _person("Ann", excluded=("Cara",)),
                _person("Bob"),
                _person("Cara", excluded=("Ann",)),
            )
        )


def test_single_participant_is_infeasible() -> None:
    with pytest.raises(InfeasibleProgramError, match="at least 2"):
        ExchangeSolver(seed=0).solve(_registry(_person("Ann")))


def test_same_seed_is_repeatable() -> None:
    participants = tuple(_person(name) for name in ("Ann", "Bob", "Cara", "Dan", "Eve"))
    registry = _registry(*participants)
    first = ExchangeSolver(seed=11).solve(registry)
    second = ExchangeSolver(seed=11).solve(registry)
    pairs = lambda result: [(item.giver.name, item.recipient.name) for item in result.assignments]

    assert pairs(first) == pairs(second)
    _assert_invariants(first)


def test_example_registry_has_a_complete_valid_assignment(project_root: Path) -> None:
    registry = RegistryLoader().load(project_root / "registry.csv.example")

    for seed in range(10):
        result = ExchangeSolver(seed=seed).solve(registry)
        assert result.removed == ()
        assert result.loaded_count == 9
        _assert_invariants(result)


def test_dummy_registry_has_a_complete_valid_assignment(project_root: Path) -> None:
    registry = RegistryLoader().load(project_root / "registries" / "dummy_registry.csv.example")
    ignored = {(item.participant, item.token, item.reason) for item in registry.ignored_exclusions}

    assert ignored == {("Dean", "Santa", "unknown")}
    result = ExchangeSolver(seed=3).solve(registry)
    assert result.removed == ()
    assert result.loaded_count == 16
    _assert_invariants(result)
