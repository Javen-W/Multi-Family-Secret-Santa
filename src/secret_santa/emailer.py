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

        Args:
            result: Solved pairings. Validation must already have passed.

        Raises:
            EmailDeliveryError: Live SMTP delivery failed for a giver.
        """
        price_label = self._config.price_label()
        for assignment in result.assignments:
            body = self.render(
                giver_name=assignment.giver.name,
                recipient_name=assignment.recipient.name,
                price_label=price_label,
            )
            self._deliver_one(
                giver_name=assignment.giver.name,
                recipient_address=assignment.giver.email,
                body=body,
            )

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

    def _deliver_one(self, giver_name: str, recipient_address: str, body: str) -> None:
        """Send one message, or log a skip when mock mode is on."""
        if self._config.email.mock_mode:
            logger.info("Mock mode: skipped email to %s <%s>", giver_name, recipient_address)
            return

        message = EmailMessage()
        message["Subject"] = self._config.email.subject
        message["From"] = self._config.email.from_address
        message["To"] = recipient_address
        message.set_content(body)
        self._send(message)
        logger.info("Sent email to %s <%s>", giver_name, recipient_address)

    def _send(self, message: EmailMessage) -> None:
        """Open an SMTP session and send ``message``."""
        settings = self._config.email
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
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            recipient = message["To"]
            raise EmailDeliveryError(f"Could not email {recipient}: {exc}") from exc
