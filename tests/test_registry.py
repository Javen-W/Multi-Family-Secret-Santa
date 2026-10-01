"""Registry cleaning and exclusion resolution."""

from pathlib import Path

import pytest

from secret_santa.exceptions import RegistryValidationError
from secret_santa.registry import RegistryLoader
from tests.helpers import write_registry

HEADER = "name,email,group,exclusions"


def test_cleans_whitespace_and_duplicate_tokens(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
 Bob , bob@example.com , A , " Cara , Cara "
 Cara , cara@example.com , B ,
""",
    )

    registry = RegistryLoader().load(path)

    by_name = {participant.name: participant for participant in registry.participants}
    assert set(by_name) == {"Bob", "Cara"}
    assert by_name["Bob"].email == "bob@example.com"
    assert by_name["Bob"].group == "A"
    assert by_name["Bob"].exclusion_tokens == ("Cara",)
    assert by_name["Bob"].excluded_names == frozenset({"Cara"})


def test_group_token_expands_to_members_without_recording_the_reverse(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Sarah,sarah@example.com,A,B
Emily,emily@example.com,B,
Joe,joe@example.com,B,
""",
    )

    registry = RegistryLoader().load(path)
    by_name = {participant.name: participant for participant in registry.participants}

    assert by_name["Sarah"].excluded_names == frozenset({"Emily", "Joe"})
    assert by_name["Emily"].excluded_names == frozenset()
    assert by_name["Joe"].excluded_names == frozenset()


def test_token_matching_a_name_and_a_group_excludes_both(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,ann@example.com,A,North
North,north@example.com,North,
Bea,bea@example.com,North,
""",
    )

    registry = RegistryLoader().load(path)
    ann = next(participant for participant in registry.participants if participant.name == "Ann")

    assert ann.excluded_names == frozenset({"North", "Bea"})


def test_unknown_and_self_tokens_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,ann@example.com,A,"Ann,NotAPerson"
Bob,bob@example.com,B,
""",
    )

    registry = RegistryLoader().load(path)
    ignored = {(item.participant, item.token, item.reason) for item in registry.ignored_exclusions}

    assert ignored == {("Ann", "Ann", "self"), ("Ann", "NotAPerson", "unknown")}
    ann = next(participant for participant in registry.participants if participant.name == "Ann")
    assert ann.excluded_names == frozenset()


def test_names_are_case_sensitive(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Bob,bob@example.com,A,bob
bob,other@example.com,B,
""",
    )

    registry = RegistryLoader().load(path)
    by_name = {participant.name: participant for participant in registry.participants}

    assert by_name["Bob"].excluded_names == frozenset({"bob"})
    assert by_name["bob"].excluded_names == frozenset()


def test_blank_rows_and_optional_columns(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        """Name,Email
Ann,ann@example.com

Bob,bob@example.com
""",
    )

    registry = RegistryLoader().load(path)

    assert [participant.name for participant in registry.participants] == ["Ann", "Bob"]
    assert all(participant.group is None for participant in registry.participants)
    assert all(participant.exclusion_tokens == () for participant in registry.participants)


def test_duplicate_name_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,ann@example.com,A,
Ann,other@example.com,B,
""",
    )

    with pytest.raises(RegistryValidationError, match="Duplicate participant name"):
        RegistryLoader().load(path)


def test_missing_email_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,,A,
""",
    )

    with pytest.raises(RegistryValidationError, match="missing email"):
        RegistryLoader().load(path)


def test_invalid_email_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,not-an-email,A,
""",
    )

    with pytest.raises(RegistryValidationError, match="invalid email"):
        RegistryLoader().load(path)


def test_unquoted_exclusion_commas_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        f"""{HEADER}
Ann,ann@example.com,A,Bob,Cara
Bob,bob@example.com,B,
Cara,cara@example.com,C,
""",
    )

    with pytest.raises(RegistryValidationError, match="must be quoted"):
        RegistryLoader().load(path)


def test_missing_required_column_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(path, "name,group\nAnn,A\n")

    with pytest.raises(RegistryValidationError, match="email"):
        RegistryLoader().load(path)


def test_empty_registry_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "people.csv"
    write_registry(path, HEADER)

    with pytest.raises(RegistryValidationError, match="no participants"):
        RegistryLoader().load(path)


def test_example_registry_loads_known_people(project_root: Path) -> None:
    registry = RegistryLoader().load(project_root / "registry.csv.example")
    names = [participant.name for participant in registry.participants]

    assert names == ["Bob", "Sarah", "Emily", "Sean", "Joe", "Tom", "Frank", "Alice", "Michael"]
    sarah = next(participant for participant in registry.participants if participant.name == "Sarah")
    assert sarah.excluded_names == frozenset({"Emily", "Sean", "Joe"})
