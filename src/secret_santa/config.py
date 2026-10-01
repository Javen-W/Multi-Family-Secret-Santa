"""YAML program configuration."""

from dataclasses import dataclass
from pathlib import Path

import yaml

from secret_santa.exceptions import ConfigValidationError
from secret_santa.models import is_valid_email

REQUIRED_TEMPLATE_FIELDS: tuple[str, ...] = (
    "{giver_name}",
    "{recipient_name}",
    "{price_limit}",
)


@dataclass(frozen=True)
class EmailSettings:
    """How assignment messages are rendered and delivered.

    Attributes:
        subject: Message subject. It is not personalized, so a preview cannot leak a recipient.
        template: Body template with ``{giver_name}``, ``{recipient_name}``, and ``{price_limit}``.
        mock_mode: When true, messages are recorded in the log and no SMTP connection is opened.
        from_address: Sender address used for live delivery.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port.
        smtp_username: SMTP username. An API key belongs here when the provider uses SMTP AUTH.
        smtp_password: SMTP password or API key. Required when a username is set and mail is live.
        use_tls: Whether to upgrade the connection with STARTTLS.
        timeout_seconds: Socket timeout for the SMTP conversation.
    """

    subject: str
    template: str
    mock_mode: bool
    from_address: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    use_tls: bool
    timeout_seconds: float


@dataclass(frozen=True)
class ProgramConfig:
    """Hyperparameters for one gift-exchange run.

    Attributes:
        registry_path: Resolved CSV path.
        gift_price_limit: Maximum gift price in ``currency`` units.
        currency: ISO-style currency label used when formatting the price reminder.
        seed: Optional RNG seed. ``None`` draws a different assignment on each run.
        log_level: Logging level name.
        email: Delivery settings.
        source_path: Config file these values were loaded from.
    """

    registry_path: Path
    gift_price_limit: int
    currency: str
    seed: int | None
    log_level: str
    email: EmailSettings
    source_path: Path

    def price_label(self) -> str:
        """Return the price limit as it should appear in mail and the organizer log."""
        if self.currency.upper() == "USD":
            return f"${self.gift_price_limit}"
        return f"{self.gift_price_limit} {self.currency}"

    def email_mode(self) -> str:
        """Return ``mock`` or ``live`` for the organizer log."""
        if self.email.mock_mode:
            return "mock"
        return "live"

    @classmethod
    def load(cls, path: str | Path) -> "ProgramConfig":
        """Load and validate a YAML config file.

        Relative registry paths are resolved from the config file's directory.

        Args:
            path: Path to the YAML file.

        Returns:
            A validated config.

        Raises:
            ConfigValidationError: The file cannot be read or a setting is invalid.
        """
        config_path = Path(path)
        payload = _read_yaml_mapping(config_path)
        registry_path = _resolve_registry_path(config_path, payload)
        email = _read_email_settings(payload)
        return cls(
            registry_path=registry_path,
            gift_price_limit=_read_price_limit(payload),
            currency=_read_currency(payload),
            seed=_read_seed(payload),
            log_level=_read_log_level(payload),
            email=email,
            source_path=config_path.resolve(),
        )


def _read_yaml_mapping(config_path: Path) -> dict[str, object]:
    """Return the top-level YAML mapping from ``config_path``."""
    if not config_path.is_file():
        raise ConfigValidationError(f"Config file not found: {config_path}")
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigValidationError(f"Could not parse config file {config_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigValidationError(f"Config file must be a mapping: {config_path}")
    return loaded


def _resolve_registry_path(config_path: Path, payload: dict[str, object]) -> Path:
    """Resolve ``registry_path`` and require that the CSV exists."""
    raw_path = payload.get("registry_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ConfigValidationError("registry_path is required and must be a file path.")
    registry_path = Path(raw_path.strip())
    if not registry_path.is_absolute():
        registry_path = config_path.parent / registry_path
    registry_path = registry_path.resolve()
    if not registry_path.is_file():
        raise ConfigValidationError(f"Registry file not found: {registry_path}")
    return registry_path


def _read_price_limit(payload: dict[str, object]) -> int:
    """Return a positive integer gift price limit."""
    raw_limit = payload.get("gift_price_limit")
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit < 1:
        raise ConfigValidationError("gift_price_limit must be a positive integer.")
    return raw_limit


def _read_currency(payload: dict[str, object]) -> str:
    """Return the currency label, defaulting to USD."""
    raw_currency = payload.get("currency", "USD")
    if not isinstance(raw_currency, str) or not raw_currency.strip():
        raise ConfigValidationError("currency must be a non-empty string.")
    return raw_currency.strip().upper()


def _read_seed(payload: dict[str, object]) -> int | None:
    """Return the optional RNG seed."""
    if "seed" not in payload or payload["seed"] is None:
        return None
    raw_seed = payload["seed"]
    if isinstance(raw_seed, bool) or not isinstance(raw_seed, int):
        raise ConfigValidationError("seed must be an integer or null.")
    return raw_seed


def _read_log_level(payload: dict[str, object]) -> str:
    """Return an uppercase logging level name."""
    raw_level = payload.get("log_level", "INFO")
    if not isinstance(raw_level, str) or not raw_level.strip():
        raise ConfigValidationError("log_level must be a logging level name.")
    return raw_level.strip().upper()


def _read_email_settings(payload: dict[str, object]) -> EmailSettings:
    """Validate the ``email`` mapping."""
    raw_email = payload.get("email")
    if not isinstance(raw_email, dict):
        raise ConfigValidationError("email settings are required and must be a mapping.")

    subject = _required_text(raw_email, "subject")
    template = _required_text(raw_email, "template")
    missing_fields = [field for field in REQUIRED_TEMPLATE_FIELDS if field not in template]
    if missing_fields:
        joined = ", ".join(missing_fields)
        raise ConfigValidationError(f"email.template is missing placeholder(s): {joined}")

    mock_mode = raw_email.get("mock_mode")
    if not isinstance(mock_mode, bool):
        raise ConfigValidationError("email.mock_mode is required and must be true or false.")

    from_address = _optional_text(raw_email, "from_address")
    smtp_host = _optional_text(raw_email, "smtp_host")
    smtp_username = _optional_text(raw_email, "smtp_username")
    smtp_password = _optional_text(raw_email, "smtp_password")
    smtp_port = _read_port(raw_email)
    use_tls = _read_use_tls(raw_email)
    timeout_seconds = _read_timeout(raw_email)

    if not mock_mode:
        if not from_address or not is_valid_email(from_address):
            raise ConfigValidationError("email.from_address must be a valid address when mock_mode is false.")
        if not smtp_host:
            raise ConfigValidationError("email.smtp_host is required when mock_mode is false.")
        if smtp_username and not smtp_password:
            raise ConfigValidationError("email.smtp_password is required when smtp_username is set.")
    elif from_address and not is_valid_email(from_address):
        raise ConfigValidationError("email.from_address must be a valid address when it is set.")

    return EmailSettings(
        subject=subject,
        template=template,
        mock_mode=mock_mode,
        from_address=from_address,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_username,
        smtp_password=smtp_password,
        use_tls=use_tls,
        timeout_seconds=timeout_seconds,
    )


def _required_text(mapping: dict[str, object], key: str) -> str:
    """Return a non-empty string field from an email mapping."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"email.{key} is required and must be a non-empty string.")
    return value.strip() if key == "subject" else value


def _optional_text(mapping: dict[str, object], key: str) -> str:
    """Return a string field, treating null and absence as empty."""
    value = mapping.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ConfigValidationError(f"email.{key} must be a string.")
    return value.strip()


def _read_port(mapping: dict[str, object]) -> int:
    """Return the SMTP port, defaulting to 587."""
    raw_port = mapping.get("smtp_port", 587)
    if isinstance(raw_port, bool) or not isinstance(raw_port, int) or not 1 <= raw_port <= 65535:
        raise ConfigValidationError("email.smtp_port must be an integer from 1 to 65535.")
    return raw_port


def _read_use_tls(mapping: dict[str, object]) -> bool:
    """Return whether STARTTLS is enabled, defaulting to true."""
    raw_tls = mapping.get("use_tls", True)
    if not isinstance(raw_tls, bool):
        raise ConfigValidationError("email.use_tls must be true or false.")
    return raw_tls


def _read_timeout(mapping: dict[str, object]) -> float:
    """Return the SMTP timeout in seconds, defaulting to 30."""
    raw_timeout = mapping.get("timeout_seconds", 30)
    if isinstance(raw_timeout, bool) or not isinstance(raw_timeout, (int, float)) or raw_timeout <= 0:
        raise ConfigValidationError("email.timeout_seconds must be a positive number.")
    return float(raw_timeout)
