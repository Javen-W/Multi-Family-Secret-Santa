"""End-to-end runs, delivery, and the organizer log."""

import logging
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

import pytest

from secret_santa.cli import main
from secret_santa.exceptions import EmailDeliveryError, InfeasibleProgramError, SecretSantaError
from secret_santa.models import Assignment, AssignmentChecks, Participant, SolveResult
from secret_santa.program import run_program
from tests.helpers import write_config, write_registry

HEADER = "name,email,group,exclusions"


class FakeSMTP:
    """Stand-in SMTP client that records messages instead of opening a socket."""

    sessions: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.messages: list[EmailMessage] = []
        FakeSMTP.sessions.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.credentials = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.messages.append(message)


class BrokenSMTP(FakeSMTP):
    """SMTP client whose first send fails."""

    def send_message(self, message: EmailMessage) -> None:
        raise OSError("mailbox unavailable")


def _messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("secret_santa")
    ]


def _write_trio(directory: Path, *, exclusion: str = "") -> Path:
    registry_path = directory / "people.csv"
    write_registry(
        registry_path,
        f"""{HEADER}
Ann,ann@example.com,North,{exclusion}
Bob,bob@example.com,South,
Cara,cara@example.com,East,
""",
    )
    return registry_path


def test_organizer_log_lists_pairings_in_mock_and_live_modes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = _write_trio(tmp_path, exclusion="NotAPerson")

    for mock_mode in (True, False):
        caplog.clear()
        FakeSMTP.sessions.clear()
        config_path = tmp_path / f"config-{mock_mode}.yaml"
        write_config(config_path, registry_path, mock_mode=mock_mode, seed=2)
        with patch("secret_santa.emailer.smtplib.SMTP", FakeSMTP):
            result = run_program(config_path)

        messages = _messages(caplog)
        mode = "mock" if mock_mode else "live"
        assert f"{'Email mode:':<24}{mode}" in messages
        assert f"{'Price limit:':<24}$100" in messages
        assert f"{'Random seed:':<24}2" in messages
        assert f"{'Participants loaded:':<24}3" in messages
        assert f"{'Permutation:':<24}ok" in messages
        assert f"{'No self-assignments:':<24}ok" in messages
        assert f"{'Exclusions respected:':<24}ok" in messages
        assert any("Ann: NotAPerson (unknown)" in message for message in messages)
        assert "Validation" in messages
        pairing_lines = [
            (
                f"{assignment.giver.name} ({assignment.giver.group_label()}) -> "
                f"{assignment.recipient.name} ({assignment.recipient.group_label()})"
            )
            for assignment in result.assignments
        ]
        assert len(pairing_lines) == 3
        for line in pairing_lines:
            assert line in messages
        email_indexes = [index for index, message in enumerate(messages) if "email to" in message]
        pairing_indexes = [messages.index(line) for line in pairing_lines]
        assert email_indexes
        assert max(pairing_indexes) < min(email_indexes)
        if mock_mode:
            assert FakeSMTP.sessions == []
            assert any(message.startswith("Mock mode: skipped email to Ann") for message in messages)
        else:
            assert len(FakeSMTP.sessions) == 1
            assert FakeSMTP.sessions[0].started_tls is True
            assert FakeSMTP.sessions[0].credentials == ("user", "secret")


def test_live_email_contains_recipient_and_price_but_not_the_secret_giver(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = _write_trio(tmp_path)
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, mock_mode=False, seed=5)
    FakeSMTP.sessions.clear()

    with patch("secret_santa.emailer.smtplib.SMTP", FakeSMTP):
        result = run_program(config_path)

    sent = {message["To"]: message for message in FakeSMTP.sessions[0].messages}
    giver_of = {assignment.recipient.name: assignment.giver.name for assignment in result.assignments}
    assert len(sent) == 3
    for assignment in result.assignments:
        message = sent[assignment.giver.email]
        body = message.get_content()
        assert message["Subject"] == "Your Secret Santa assignment"
        assert assignment.recipient.name not in message["Subject"]
        assert assignment.recipient.name in body
        assert "$100" in body
        secret_giver = giver_of[assignment.giver.name]
        assert secret_giver != assignment.recipient.name
        assert secret_giver not in body


def test_removed_participant_is_named_in_the_program_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = tmp_path / "people.csv"
    write_registry(
        registry_path,
        f"""{HEADER}
Ann,ann@example.com,North,
Bob,bob@example.com,South,
Cara,cara@example.com,East,
Zoe,zoe@example.com,West,"Ann,Bob,Cara"
""",
    )
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, seed=1)

    result = run_program(config_path)

    assert [item.name for item in result.removed] == ["Zoe"]
    messages = _messages(caplog)
    assert any("Zoe: no legal giver or recipient" in message for message in messages)
    assert f"{'Participants removed:':<24}1" in messages
    assert f"{'Participants assigned:':<24}3" in messages
    assert sum(" -> " in message for message in messages) == 3


def test_missing_group_removes_the_participant_before_email(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = tmp_path / "people.csv"
    write_registry(
        registry_path,
        f"""{HEADER}
Ann,ann@example.com,North,
Bob,bob@example.com,South,
Zoe,zoe@example.com,,
""",
    )
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, seed=1)

    result = run_program(config_path)

    assert result.loaded_count == 3
    assert [(item.name, item.reason) for item in result.removed] == [("Zoe", "missing group")]
    assert {assignment.giver.name for assignment in result.assignments} == {"Ann", "Bob"}
    messages = _messages(caplog)
    assert any("Zoe: missing group" in message for message in messages)
    assert not any("skipped email to Zoe" in message for message in messages)
    assert sum(" -> " in message for message in messages) == 2


def test_infeasible_program_sends_no_email(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = tmp_path / "people.csv"
    write_registry(
        registry_path,
        f"""{HEADER}
Ann,ann@example.com,A,Cara
Bob,bob@example.com,B,
Cara,cara@example.com,C,Ann
""",
    )
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path)

    with patch("secret_santa.program.AssignmentMailer") as mailer_cls:
        with pytest.raises(InfeasibleProgramError):
            run_program(config_path)

    mailer_cls.assert_not_called()
    assert "Assignments" not in _messages(caplog)


def test_failed_validation_sends_no_email(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = _write_trio(tmp_path)
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path)
    ann = Participant("Ann", "ann@example.com", "North", (), frozenset())
    bob = Participant("Bob", "bob@example.com", "South", (), frozenset())
    failed = SolveResult(
        assignments=(Assignment(giver=ann, recipient=ann), Assignment(giver=bob, recipient=bob)),
        loaded_count=3,
        removed=(),
        ignored_exclusions=(),
        checks=AssignmentChecks(False, False, False),
    )

    with patch("secret_santa.program.ExchangeSolver.solve", return_value=failed):
        with patch("secret_santa.program.AssignmentMailer") as mailer_cls:
            with pytest.raises(SecretSantaError, match="failed validation"):
                run_program(config_path)

    mailer_cls.assert_not_called()
    messages = _messages(caplog)
    assert f"{'Permutation:':<24}failed" in messages
    assert "Ann (North) -> Ann (North)" in messages


def test_smtp_failure_is_reported_after_the_organizer_log(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = _write_trio(tmp_path)
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, mock_mode=False, seed=1)
    FakeSMTP.sessions.clear()

    with patch("secret_santa.emailer.smtplib.SMTP", BrokenSMTP):
        with pytest.raises(EmailDeliveryError, match="Could not email"):
            run_program(config_path)

    messages = _messages(caplog)
    assert any(" -> " in message for message in messages)
    assert not any(message.startswith("Sent email to") for message in messages)


def test_cli_returns_success_and_logs_the_program(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = _write_trio(tmp_path)
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, seed=1)

    status = main(["--config", str(config_path)])

    assert status == 0
    assert "Secret Santa program" in _messages(caplog)
    assert any(" -> " in message for message in _messages(caplog))


def test_cli_returns_failure_for_an_infeasible_program(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")
    registry_path = tmp_path / "people.csv"
    write_registry(registry_path, "name,email\nAnn,ann@example.com\n")
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path)

    status = main(["--config", str(config_path)])

    assert status == 1
    assert any("at least 2" in message for message in _messages(caplog))


def test_shipped_example_config_solves_the_dummy_registry(
    project_root: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="secret_santa")

    result = run_program(project_root / "config.yaml.example")

    assert len(result.assignments) == 16
    assert result.removed == ()
    messages = _messages(caplog)
    assert f"{'Email mode:':<24}mock" in messages
    assert f"{'Participants assigned:':<24}16" in messages
    assert any("Dean: Santa (unknown)" in message for message in messages)
    assert sum(" -> " in message for message in messages) == 16
    assert any(message.startswith("Mock mode: skipped email to ") for message in messages)
