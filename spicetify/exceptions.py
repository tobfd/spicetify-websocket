class SpicetifyError(Exception):
    """Base exception for all errors raised by this library."""


class NotConnectedError(SpicetifyError):
    """Raised when an action is attempted without an active connection.

    Args:
        message: Human-readable error message.
    """

    def __init__(self, message="No active connection to Spicetify is available."):
        super().__init__(message)


class RequestTimeoutError(SpicetifyError):
    """Raised when Spotify does not respond to a command in time.

    Args:
        command: Name of the command that timed out.
        timeout: Timeout value in seconds.
    """

    def __init__(self, command: str, timeout: float):
        self.command = command
        self.timeout = timeout
        super().__init__(f"Command '{command}' did not respond within {timeout}s.")
