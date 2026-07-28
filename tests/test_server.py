"""Tests for the SpotifyServer class, commands, and event dispatching."""

import asyncio
from unittest.mock import MagicMock

import pytest

from spicetify import (
    NotConnectedError,
    PlayerState,
    RepeatMode,
    RequestTimeoutError,
    SpotifyServer,
    TrackInfo,
)
from spicetify.models import PlayRequest


@pytest.mark.asyncio
async def test_event_registration_and_dispatch():
    """Test registering an event handler and dispatching a song changed event."""
    server = SpotifyServer()
    received_tracks = []

    @server.on_song_changed
    async def on_song(track: TrackInfo):
        received_tracks.append(track)

    raw_payload = {
        "track": {
            "uri": "spotify:track:xyz",
            "name": "Async Track",
            "duration": 120000,
            "artists": [],
            "album": {"name": "Album", "uri": "spotify:album:1"},
        }
    }

    await server._dispatch_event("SongChanged", raw_payload)
    await asyncio.sleep(0)

    assert len(received_tracks) == 1
    assert received_tracks[0].title == "Async Track"


@pytest.mark.asyncio
async def test_convenience_decorators_registration():
    """Ensure all convenience decorators register callbacks correctly."""
    server = SpotifyServer()

    @server.on_initial_state
    def h1(_):
        pass

    @server.on_play_pause_changed
    def h2(_):
        pass

    @server.on_volume_changed
    def h3(_):
        pass

    @server.on_repeat_changed
    def h4(_):
        pass

    @server.on_shuffle_changed
    def h5(_):
        pass

    @server.on_seek_changed
    def h6(_):
        pass

    assert "initialstate" in server._event_callbacks
    assert "playpausechanged" in server._event_callbacks
    assert "volumechanged" in server._event_callbacks
    assert "repeatchanged" in server._event_callbacks
    assert "shufflechanged" in server._event_callbacks
    assert "seekchanged" in server._event_callbacks


@pytest.mark.asyncio
async def test_commands_without_connection_raise_error():
    """Ensure sending commands when disconnected raises NotConnectedError."""
    server = SpotifyServer()

    with pytest.raises(NotConnectedError):
        await server.play()

    with pytest.raises(NotConnectedError):
        await server.get_volume()


@pytest.mark.asyncio
async def test_parse_event_payloads():
    """Test parsing various event payloads into models and primitives."""
    p_init = SpotifyServer._parse_event_payload("InitialState", {"playerData": {"isPaused": False}})
    assert isinstance(p_init, PlayerState)

    p_pp = SpotifyServer._parse_event_payload(
        "PlayPauseChanged", {"playerState": {"isPaused": True}}
    )
    assert isinstance(p_pp, PlayerState)

    p_repeat = SpotifyServer._parse_event_payload("RepeatChanged", {"mode": 2})
    assert p_repeat == RepeatMode.TRACK

    p_shuffle = SpotifyServer._parse_event_payload("ShuffleChanged", {"state": True})
    assert p_shuffle is True

    p_seek = SpotifyServer._parse_event_payload("SeekChanged", {"position": 5000})
    assert p_seek == 5000

    p_unknown = SpotifyServer._parse_event_payload("CustomEvent", {"data": 123})
    assert p_unknown == {"data": 123}


@pytest.mark.asyncio
async def test_all_server_playback_methods_with_mock(monkeypatch):
    """Test all server API commands by mocking _send_command responses."""
    server = SpotifyServer()
    server.websocket = MagicMock()  # Fixed Warning 1: Use MagicMock instead of object()

    sent_requests = []

    # Fixed Warning 2: Renamed unused parameter timeout to _timeout
    async def mock_send_command(request, _timeout=5.0):
        sent_requests.append(request)
        name = request.requestName

        if name == "GetVolume":
            return {"payload": {"level": 0.8}}
        if name == "GetPlayPause":
            return {"payload": {"isPlaying": True}}
        if name == "GetPlayerState":
            return {
                "payload": {
                    "playerData": {
                        "isPaused": False,
                        "positionAsOfTimestamp": 1000,
                        "duration": 200000,
                    }
                }
            }
        if name == "GetCurrentTrack":
            return {"payload": {"track": {"name": "Current Track", "uri": "spotify:track:123"}}}
        return {"success": True}

    monkeypatch.setattr(server, "_send_command", mock_send_command)

    # Test all playback methods
    await server.play()
    await server.pause()
    await server.toggle_play()
    await server.next_song()
    await server.previous_song()
    await server.previous_song(force=True)

    await server.set_volume(75.0)
    await server.set_repeat(RepeatMode.TRACK)
    await server.set_shuffle(True)
    await server.set_mute(False)

    await server.play_uri("spotify:track:abc")
    await server.play_url("https://spotify.com/track")
    await server.seek(15000)

    # Test state query methods
    vol = await server.get_volume()
    assert vol == 80.0

    is_playing = await server.get_is_playing()
    assert is_playing is True

    state = await server.get_player_state()
    assert isinstance(state, PlayerState)

    track = await server.get_current_track()
    assert isinstance(track, TrackInfo)
    assert track.title == "Current Track"


@pytest.mark.asyncio
async def test_server_command_validation_errors(monkeypatch):
    """Test parameter validation errors in server methods."""
    server = SpotifyServer()
    server.websocket = MagicMock()

    with pytest.raises(ValueError):
        await server.set_volume(-10)

    with pytest.raises(ValueError):
        await server.set_volume(105)

    with pytest.raises(ValueError):
        await server.seek(-100)


@pytest.mark.asyncio
async def test_server_lifecycle_and_timeouts():
    """Test server start, stop, and connection timeout handling."""
    server = SpotifyServer(port=9098)
    await server.start()
    assert server.server is not None

    # Test wait_for_connection when already connected
    server.websocket = MagicMock()
    await server.wait_for_connection()

    # Test wait_for_connection timeout when disconnected
    server.websocket = None
    with pytest.raises(NotConnectedError):
        await server.wait_for_connection(timeout=0.01)

    await server.stop()


@pytest.mark.asyncio
async def test_server_dispatch_callback_exception():
    """Test exception handling during event dispatching for sync functions."""
    server = SpotifyServer()

    @server.on("SongChanged")
    def failing_callback(_):
        raise RuntimeError("Simulated error in user callback")

    # Should catch the error internally, log it, and not crash
    await server._dispatch_event("SongChanged", {})


@pytest.mark.asyncio
async def test_send_command_timeout():
    """Test RequestTimeoutError when Spotify doesn't respond in time."""
    server = SpotifyServer()
    server.websocket = MagicMock()
    server.websocket.send = MagicMock(side_effect=lambda msg: asyncio.sleep(0))

    # _send_command creates a future that is never resolved, triggering a timeout
    with pytest.raises(RequestTimeoutError):
        await server._send_command(PlayRequest(), timeout=0.01)
