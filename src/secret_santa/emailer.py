"""Render and deliver one assignment email per giver."""

import logging
import smtplib
from email.message import EmailMessage

from secret_santa.config import ProgramConfig
from secret_santa.exceptions import ConfigValidationError, EmailDeliveryError
from secret_santa.models import SolveResult

logger = logging.getLogger("secret_santa.emailer")


class AssignmentMailer:
    """Send each giver only their own recipient and the price reminder.

    Message bodies are rendered from the configured template. They do not include
    the rest of the matching, so a participant cannot learn who is giving to them
    unless that person is also their recipient.
    """

    def __init__(self, config: ProgramConfig) -> None:
        """Create a mailer bound to one program config.

        Args:
            config: Email template, price limit, and SMTP or mock settings.
        """
        self._config = config

    def deliver(self, result: SolveResult) -> None:
        """Deliver every assignment in giver-name order.

        Live delivery uses one SMTP session for the whole program. Mock mode
        records a skip for each giver and does not open a connection.

        Args:
            result: Solved pairings. Validation must already have passed.

        Raises:
            EmailDeliveryError: Live SMTP delivery failed for a giver.
        """
        price_label = self._config.price_label()
        messages = [
            (
                assignment.giver.name,
                assignment.giver.email,
                self.render(
                    giver_name=assignment.giver.name,
                    recipient_name=assignment.recipient.name,
                    price_label=price_label,
                ),
            )
            for assignment in result.assignments
        ]
        if self._config.email.mock_mode:
            for giver_name, recipient_address, _body in messages:
                logger.info("Mock mode: skipped email to %s <%s>", giver_name, recipient_address)
            return
        self._send_all(messages)

    def render(self, giver_name: str, recipient_name: str, price_label: str) -> str:
        """Fill the template for a single giver.

        Args:
            giver_name: Person receiving this message.
            recipient_name: Person they will buy a gift for.
            price_label: Formatted price limit, such as ``$100``.

        Returns:
            The message body.
        """
        try:
            return self._config.email.template.format(
                giver_name=giver_name,
                recipient_name=recipient_name,
                price_limit=price_label,
            )
        except (IndexError, KeyError, ValueError) as exc:
            raise ConfigValidationError(f"email.template could not be rendered: {exc}") from exc

    def _send_all(self, messages: list[tuple[str, str, str]]) -> None:
        """Open one SMTP session and send every rendered message.

        Args:
            messages: Tuples of giver name, giver email, and message body.

        Raises:
            EmailDeliveryError: The server could not accept a message.
        """
        settings = self._config.email
        # None until a recipient is attempted, so a connection failure is not
        # described as a failed message to a person.
        current_address: str | None = None
        try:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.timeout_seconds,
            ) as smtp:
                if settings.use_tls:
                    smtp.starttls()
                if settings.smtp_username:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                for giver_name, recipient_address, body in messages:
                    current_address = recipient_address
                    message = EmailMessage()
                    message["Subject"] = settings.subject
                    message["From"] = settings.from_address
                    message["To"] = recipient_address
                    message.set_content(body)
                    smtp.send_message(message)
                    logger.info("Sent email to %s <%s>", giver_name, recipient_address)
        except (OSError, smtplib.SMTPException) as exc:
            if current_address is None:
                raise EmailDeliveryError(f"Could not connect to {settings.smtp_host}: {exc}") from exc
            raise EmailDeliveryError(f"Could not email {current_address}: {exc}") from exc
