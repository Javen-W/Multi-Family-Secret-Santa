"""YAML config validation."""

from pathlib import Path

import pytest

from secret_santa.config import ProgramConfig
from secret_santa.exceptions import ConfigValidationError
from tests.helpers import write_config, write_registry


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "people.csv"
    write_registry(
        path,
        """name,email
Ann,ann@example.com
Bob,bob@example.com
""",
    )
    return path


def test_loads_settings_and_formats_usd_price(tmp_path: Path) -> None:
    registry_path = _registry(tmp_path)
    config_path = tmp_path / "config.yaml"
    write_config(config_path, registry_path, seed=7, price=40)

    config = ProgramConfig.load(config_path)

    assert config.registry_path == registry_path.resolve()
    assert config.gift_price_limit == 40
    assert config.price_label() == "$40"
    assert config.seed == 7
    assert config.email_mode() == "mock"
    assert config.email.subject == "Your Secret Santa assignment"


def test_relative_registry_path_is_resolved_from_the_config_directory(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    write_registry(
        nested / "people.csv",
        """name,email
Ann,ann@example.com
Bob,bob@example.com
""",
    )
    config_path = nested / "config.yaml"
    config_path.write_text(
        """
registry_path: people.csv
gift_price_limit: 25
currency: EUR
seed: null
email:
  subject: Assignment
  mock_mode: true
  template: |
    {giver_name} gives to {recipient_name} within {price_limit}.
""",
        encoding="utf-8",
    )

    config = ProgramConfig.load(config_path)

    assert config.registry_path == (nested / "people.csv").resolve()
    assert config.price_label() == "25 EUR"
    assert config.seed is None
    assert config.log_level == "INFO"


def test_missing_config_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigValidationError, match="not found"):
        ProgramConfig.load(tmp_path / "missing.yaml")


def test_missing_registry_file_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
registry_path: missing.csv
gift_price_limit: 10
email:
  subject: Assignment
  mock_mode: true
  template: "{giver_name} {recipient_name} {price_limit}"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Registry file not found"):
        ProgramConfig.load(config_path)


def test_non_positive_price_is_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, _registry(tmp_path))
    text = config_path.read_text(encoding="utf-8").replace("gift_price_limit: 100", "gift_price_limit: 0")
    config_path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="gift_price_limit"):
        ProgramConfig.load(config_path)


def test_template_must_include_required_placeholders(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, _registry(tmp_path), template="Hello {giver_name}\n")

    with pytest.raises(ConfigValidationError, match="price_limit"):
        ProgramConfig.load(config_path)


def test_live_mode_requires_smtp_host(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, _registry(tmp_path), mock_mode=False)
    text = config_path.read_text(encoding="utf-8").replace("smtp.example.com", '""')
    config_path.write_text(text, encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="smtp_host"):
        ProgramConfig.load(config_path)


def test_shipped_example_config_is_mock_mode(project_root: Path) -> None:
    config = ProgramConfig.load(project_root / "config.yaml.example")

    assert config.email.mock_mode is True
    assert config.gift_price_limit == 100
    assert config.price_label() == "$100"
    assert config.registry_path.name == "dummy_registry.csv.example"
