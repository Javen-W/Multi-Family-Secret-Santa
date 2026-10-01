"""Errors raised while preparing or running a Secret Santa program."""


class SecretSantaError(Exception):
    """Base error for Secret Santa configuration, data, and solving failures."""


class ConfigValidationError(SecretSantaError):
    """Raised when the YAML config is missing settings or has invalid values."""


class RegistryValidationError(SecretSantaError):
    """Raised when the registry CSV is missing required data or is inconsistent."""


class InfeasibleProgramError(SecretSantaError):
    """Raised when the remaining participants have no complete assignment."""


class EmailDeliveryError(SecretSantaError):
    """Raised when an assignment email cannot be delivered."""
