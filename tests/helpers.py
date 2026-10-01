"""File builders shared by tests."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_registry(path: Path, body: str) -> None:
    """Write a CSV registry, adding a trailing newline when missing."""
    text = body if body.endswith("\n") else f"{body}\n"
    path.write_text(text, encoding="utf-8")


def write_config(
    path: Path,
    registry_path: Path,
    *,
    mock_mode: bool = True,
    seed: int | None = 1,
    price: int = 100,
    currency: str = "USD",
    template: str | None = None,
) -> None:
    """Write a valid YAML config that points at ``registry_path``."""
    seed_text = "null" if seed is None else str(seed)
    mock_text = "true" if mock_mode else "false"
    body = template if template is not None else (
        "Hello {giver_name},\n"
        "You are giving a gift to {recipient_name}.\n"
        "The price limit is {price_limit}.\n"
    )
    indented_template = "\n".join(f"    {line}" if line else "" for line in body.splitlines())
    path.write_text(
        "\n".join(
            [
                f'registry_path: "{registry_path}"',
                f"gift_price_limit: {price}",
                f"currency: {currency}",
                f"seed: {seed_text}",
                "log_level: INFO",
                "email:",
                "  subject: Your Secret Santa assignment",
                f"  mock_mode: {mock_text}",
                "  from_address: santa@example.com",
                "  smtp_host: smtp.example.com",
                "  smtp_port: 587",
                "  smtp_username: user",
                "  smtp_password: secret",
                "  use_tls: true",
                "  template: |",
                indented_template,
                "",
            ]
        ),
        encoding="utf-8",
    )
