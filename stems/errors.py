class StemsError(Exception):
    """Base error for the stems application."""


class DependencyError(StemsError):
    """Raised when an optional runtime dependency is unavailable."""


class AbletonConnectionError(StemsError):
    """Raised when AbletonOSC is unavailable or unresponsive."""


class ProjectDetectionError(StemsError):
    """Raised when the current Ableton project cannot be resolved."""


class ExportAutomationError(StemsError):
    """Raised when UI automation fails during export."""


class PreflightCheckError(StemsError):
    """Raised when the environment is not ready for export."""
