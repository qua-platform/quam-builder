# --- Custom Exceptions ---
class VoltageSequenceError(Exception):
    """Base class for errors in this module."""

    pass


class StateError(VoltageSequenceError):
    """Errors related to the sequence state."""

    pass


# --- Custom Exceptions ---


class ConfigurationError(VoltageSequenceError):
    """Errors related to the QUA configuration dictionary."""

    pass


class VoltagePointError(VoltageSequenceError):
    """Errors related to named voltage points."""

    pass
