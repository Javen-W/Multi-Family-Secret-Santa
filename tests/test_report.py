"""Organizer report contents."""

from pathlib import Path

import pytest

from secret_santa.config import EmailSettings, ProgramConfig
from secret_santa.models import (
    Assignment,
    AssignmentChecks,
    IgnoredExclusion,
    Participant,
    RemovedParticipant,
    SolveResult,
)
from secret_santa.report import ProgramReporter


def _participant(name: str, group: str) -> Participant:
    return Participant(
        name=name,
        email=f"{name.lower()}@example.com",
        group=group,
        exclusion_tokens=(),
        excluded_names=frozenset(),
    )


def _config(mode_mock: bool) -> ProgramConfig:
    return ProgramConfig(
        registry_path=Path("/registries/people.csv"),
        gift_price_limit=100,
        currency="USD",
        seed=None,
        log_level="INFO",
        source_path=Path("/config.yaml"),
        email=EmailSettings(
            subject="Assignment",
            template="{giver_name} {recipient_name} {price_limit}",
            mock_mode=mode_mock,
            from_address="santa@example.com",
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="",
            smtp_password="",
            use_tls=True,
            timeout_seconds=30,
        ),
    )


def _result() -> SolveResult:
    ann = _participant("Ann", "A")
    bob = _participant("Bob", "B")
    return SolveResult(
        assignments=(
            Assignment(giver=bob, recipient=ann),
            Assignment(giver=ann, recipient=bob),
        ),
        loaded_count=3,
        removed=(RemovedParticipant("Zoe", "no legal recipient"),),
        ignored_exclusions=(IgnoredExclusion("Ann", "Nobody", "unknown"),),
        checks=AssignmentChecks(
            is_permutation=True,
            no_self_assignments=True,
            exclusions_respected=False,
        ),
    )


def test_report_lists_metadata_validation_and_sorted_pairings() -> None:
    text = ProgramReporter().format(_result(), _config(mode_mock=True))

    assert f"{'Registry:':<24}/registries/people.csv" in text
    assert f"{'Price limit:':<24}$100" in text
    assert f"{'Email mode:':<24}mock" in text
    assert f"{'Random seed:':<24}none" in text
    assert f"{'Participants loaded:':<24}3" in text
    assert f"{'Participants removed:':<24}1" in text
    assert f"{'Participants assigned:':<24}2" in text
    assert "Ann: Nobody (unknown)" in text
    assert "Zoe: no legal recipient" in text
    assert f"{'Permutation:':<24}ok" in text
    assert f"{'No self-assignments:':<24}ok" in text
    assert f"{'Exclusions respected:':<24}failed" in text
    assert text.index("Ann (A) -> Bob (B)") < text.index("Bob (B) -> Ann (A)")


def test_reporter_logs_every_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="secret_santa")

    ProgramReporter().log(_result(), _config(mode_mock=False))

    messages = [record.getMessage() for record in caplog.records]
    assert f"{'Email mode:':<24}live" in messages
    assert "Ann (A) -> Bob (B)" in messages
    assert "Bob (B) -> Ann (A)" in messages
