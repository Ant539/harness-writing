"""Domain error placeholders."""


class PaperHarnessError(Exception):
    """Base exception for future domain errors."""


class InvalidStateTransition(PaperHarnessError):
    """Raised when a lifecycle transition is invalid."""
