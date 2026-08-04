"""Tests for the SpotifyServer class, commands, security, and event dispatching."""

import asyncio
import json
import ssl
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from spicetify import (
    NotConnectedError,
    PlayerState,
    RepeatMode,
    RequestTimeoutError,
    SpotifyServer,
    TrackInfo,
    UnauthorizedError,
)
from spicetify.models import _PlayRequest


@pytest.mark.asyncio
async def test_event_registration_and_dispatch():
    """Test registering event handlers and dispatching PlayerState updates."""
    server = SpotifyServer()
    received_states = []
    received_wildcards = []

    @server.on_song_changed
    async def on_song(state: PlayerState):
        received_states.append(state)

    @server.on_state_changed
    def on_wildcard(state: PlayerState):
        received_wildcards.append(state)

    raw_payload = {
        "isPlaying": True,
        "volume": 0.8,
        "playerState": {
            "positionAsOfTimestamp": 5000,
            "duration": 180000,
            "item": {
                "uri": "spotify:track:xyz",
                "name": "Async Track",
                "duration": 180000,
                "artists": [],
            },
        },
    }

    await server._dispatch_event("SongChanged", raw_payload)
    await asyncio.sleep(0)

    assert len(received_states) == 1
    assert received_states[0].event_name == "SongChanged"
    assert received_states[0].track is not None
    assert received_states[0].track.title == "Async Track"

    assert len(received_wildcards) == 1
    assert received_wildcards[0].event_name == "SongChanged"


@pytest.mark.asyncio
async def test_convenience_decorators_registration():
    """Ensure all convenience decorators register callbacks correctly."""
    server = SpotifyServer()

    @server.on_state_changed
    def h0(_):
        pass

    @server.on_initial_state
    def h1(_):
        pass

    @server.on_song_changed
    def h2(_):
        pass

    @server.on_play_pause_changed
    def h3(_):
        pass

    @server.on_volume_changed
    def h4(_):
        pass

    @server.on_repeat_changed
    def h5(_):
        pass

    @server.on_shuffle_changed
    def h6(_):
        pass

    @server.on_seek_changed
    def h7(_):
        pass

    @server.on_ping
    def h8(_):
        pass

    assert "*" in server._event_callbacks
    assert "initialstate" in server._event_callbacks
    assert "songchanged" in server._event_callbacks
    assert "playpausechanged" in server._event_callbacks
    assert "volumechanged" in server._event_callbacks
    assert "repeatchanged" in server._event_callbacks
    assert "shufflechanged" in server._event_callbacks
    assert "seekchanged" in server._event_callbacks
    assert "ping" in server._event_callbacks


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
    assert p_init.event_name == "InitialState"

    p_ping = SpotifyServer._parse_event_payload("Ping", {"timestamp": 1785633863000})
    assert isinstance(p_ping, datetime)


@pytest.mark.asyncio
async def test_all_server_playback_methods_with_mock(monkeypatch):
    """Test all server API commands by mocking _send_command responses."""
    server = SpotifyServer(api_key="secret-token")
    server.websocket = MagicMock()

    sent_requests = []

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
    await server.play_url("https://open.spotify.com/track/abc")
    await server.seek(15000)

    latency = await server.ping()
    assert latency >= 0.0

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
async def test_server_command_validation_errors():
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
async def test_ssl_context_configuration():
    """Test initializing SpotifyServer with SSL settings."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server = SpotifyServer(ssl_context=ctx)
    assert server.ssl_context is ctx


@pytest.mark.asyncio
async def test_api_key_token_injection():
    """Ensure token is injected into request when api_key is set."""
    server = SpotifyServer(api_key="my-key-123")
    req = _PlayRequest()

    async def mock_send(_msg):
        fut = server._pending_requests.get(req.requestId)
        if fut and not fut.done():
            fut.set_result({"success": True})

    mock_ws = AsyncMock()
    mock_ws.send = AsyncMock(side_effect=mock_send)
    server.websocket = mock_ws

    res = await server._send_command(request=req, timeout=1.0)

    assert res == {"success": True}
    assert req.token == "my-key-123"
    assert mock_ws.send.called


@pytest.mark.asyncio
async def test_unauthorized_response_handling():
    """Test that unauthorized response sets UnauthorizedError exception."""
    server = SpotifyServer()
    server.websocket = MagicMock()

    req = _PlayRequest()
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    server._pending_requests[req.requestId] = future

    response_payload = {
        "eventName": "Response",
        "requestId": req.requestId,
        "success": False,
        "message": "Unauthorized: Invalid API Key token",
    }

    msg = json.dumps(response_payload)
    ws_mock = MagicMock()
    ws_mock.remote_address = ("127.0.0.1", 12345)

    async def msg_generator():
        yield msg

    ws_mock.__aiter__ = lambda s: msg_generator()

    await server._handler(ws_mock)

    with pytest.raises(UnauthorizedError):
        future.result()


@pytest.mark.asyncio
async def test_handler_token_filtering():
    """Test that incoming events/messages with invalid tokens are dropped."""
    server = SpotifyServer(api_key="correct-token")
    events_received = []

    @server.on("SongChanged")
    def on_song(_):
        events_received.append("song")

    msg_bad = json.dumps({"token": "wrong-token", "eventName": "SongChanged", "payload": {}})
    msg_good = json.dumps({"token": "correct-token", "eventName": "SongChanged", "payload": {}})

    async def msg_generator():
        yield msg_bad
        yield msg_good

    ws_mock = MagicMock()
    ws_mock.remote_address = ("127.0.0.1", 12345)
    ws_mock.__aiter__ = lambda s: msg_generator()

    await server._handler(ws_mock)
    await asyncio.sleep(0)

    assert len(events_received) == 1


@pytest.mark.asyncio
async def test_send_command_timeout():
    """Test RequestTimeoutError when Spotify doesn't respond in time."""
    server = SpotifyServer()
    mock_ws = AsyncMock()
    server.websocket = mock_ws

    with pytest.raises(RequestTimeoutError):
        await server._send_command(_PlayRequest(), timeout=0.01)


@pytest.mark.asyncio
async def test_server_lifecycle_and_timeouts():
    """Test server start, stop, and connection timeout handling using ephemeral port."""
    server = SpotifyServer(port=0)
    await server.start()
    assert server.server is not None

    server.websocket = MagicMock()
    await server.wait_for_connection()

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

    await server._dispatch_event("SongChanged", {})
