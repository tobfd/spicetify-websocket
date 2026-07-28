"""Tests for custom Spicetify exceptions."""

from spicetify import NotConnectedError, RequestTimeoutError, SpicetifyError


def test_exceptions_instantiation():
    """Test custom exception message formatting and properties."""
    err_not_connected = NotConnectedError()
    assert "No active connection" in str(err_not_connected)

    err_timeout = RequestTimeoutError("Play", 5.0)
    assert err_timeout.command == "Play"
    assert err_timeout.timeout == 5.0
    assert "Command 'Play' did not respond within 5.0s." in str(err_timeout)

    err_base = SpicetifyError("Base exception message")
    assert str(err_base) == "Base exception message"
