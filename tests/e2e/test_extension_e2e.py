"""End-to-end tests: the real spicetify-connect-api extension against the real server.

The extension's JavaScript runs in Node.js (``harness.js``) with a fake Spicetify
API but a real WebSocket connection to :class:`SpotifyServer`. Every message in
both directions is validated against the extension's protocol schema.

The tests are skipped unless ``SPICETIFY_EXTENSION_DIR`` points to a checkout of
https://github.com/tobfd/spicetify-connect-api and ``node`` (22+) is installed::

    SPICETIFY_EXTENSION_DIR=../spicetify-connect-api pytest tests/e2e

Tests for features of a newer protocol version are skipped when the checked-out
extension is older, so the suite also verifies compatibility with old extensions.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from spicetify import RequestFailedError, SpotifyServer

EXTENSION_DIR = os.environ.get("SPICETIFY_EXTENSION_DIR")
HERE = Path(__file__).parent
HARNESS = HERE / "harness.js"
PLAYER_DATA = HERE.parent / "fixtures" / "spicetify_player_data.json"
API_KEY = "e2e-secret"

pytestmark = pytest.mark.skipif(
    not EXTENSION_DIR or shutil.which("node") is None,
    reason="set SPICETIFY_EXTENSION_DIR to a spicetify-connect-api checkout and install Node.js",
)


def _schema_validator():
    """Return a validator for the extension's protocol schema, if it ships one."""
    schema_path = Path(EXTENSION_DIR or "") / "protocol" / "messages.schema.json"
    if not schema_path.is_file():
        return None
    from jsonschema import Draft202012Validator

    return Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))


class Extension:
    """The extension running in a Node.js subprocess."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None

    async def start(self, url: str, api_key: str = API_KEY) -> None:
        self._process = await asyncio.create_subprocess_exec(
            "node",
            str(HARNESS),
            str(Path(EXTENSION_DIR or "") / "spicetify-connect-api.js"),
            url,
            api_key,
            str(PLAYER_DATA),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        self._reader = asyncio.create_task(self._read())
        await self.wait_for(lambda: any(e["type"] == "loaded" for e in self.events))

    async def _read(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for line in self._process.stdout:
            self.events.append(json.loads(line))

    async def stop(self) -> None:
        if self._process is not None and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
        if self._reader is not None:
            await self._reader

    async def command(self, line: str) -> None:
        assert self._process is not None and self._process.stdin is not None
        count = self._count("done")
        self._process.stdin.write((line + "\n").encode())
        await self._process.stdin.drain()
        await self.wait_for(lambda: self._count("done") > count)

    async def wait_for(self, condition: Callable[[], bool], timeout: float = 5.0) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while not condition():
            if loop.time() > deadline:
                raise AssertionError("Condition was not met in time")
            await asyncio.sleep(0.02)

    def _count(self, event_type: str) -> int:
        return sum(1 for e in self.events if e["type"] == event_type)

    def calls(self, name: str) -> list[list[Any]]:
        return [e["args"] for e in self.events if e["type"] == "call" and e["name"] == name]

    def messages(self) -> list[dict[str, Any]]:
        """All frames sent and received by the extension."""
        return [e["message"] for e in self.events if e["type"] in ("sent", "received")]

    @property
    def initial_state(self) -> dict[str, Any]:
        for event in self.events:
            if event["type"] == "sent" and event["message"].get("eventName") == "InitialState":
                return event["message"]
        raise AssertionError("The extension sent no InitialState")

    @property
    def protocol_version(self) -> int:
        return self.initial_state["payload"].get("protocolVersion", 0)

    def require_protocol(self, version: int) -> None:
        if self.protocol_version < version:
            pytest.skip(
                f"needs protocol version {version}, extension speaks {self.protocol_version}"
            )


def _url(server: SpotifyServer) -> str:
    assert server.server is not None
    return f"ws://127.0.0.1:{server.server.sockets[0].getsockname()[1]}"


@pytest.fixture
async def server() -> AsyncIterator[SpotifyServer]:
    async with SpotifyServer(port=0, api_key=API_KEY) as srv:
        yield srv


@pytest.fixture
async def extension(server: SpotifyServer) -> AsyncIterator[Extension]:
    """The extension, connected and authenticated to ``server``."""
    ext = Extension()
    await ext.start(_url(server))
    try:
        await server.wait_for_connection(timeout=5)
        yield ext
    finally:
        await ext.stop()

    validator = _schema_validator()
    if validator is not None:
        problems = [
            f"{message.get('eventName') or message.get('requestName')}: {error.message}"
            for message in ext.messages()
            for error in validator.iter_errors(message)
        ]
        assert not problems, "messages violate protocol/messages.schema.json:\n" + "\n".join(
            problems
        )


async def test_extension_authenticates_and_reports_state(
    server: SpotifyServer, extension: Extension
) -> None:
    assert server.is_connected
    assert extension.initial_state["token"] == API_KEY

    state = await server.get_player_state()
    assert state.track is not None
    assert state.track.title == "Love You Like A Love Song"
    assert state.volume == 42.0


async def test_protocol_and_extension_version_are_reported(
    server: SpotifyServer, extension: Extension
) -> None:
    assert server.client_protocol_version == extension.protocol_version
    assert server.client_version == extension.initial_state["payload"].get("extensionVersion")


async def test_playback_and_volume_commands(server: SpotifyServer, extension: Extension) -> None:
    await server.play()
    await server.pause()
    await server.set_volume(50)
    await server.set_shuffle(True)

    assert extension.calls("play") == [[]]
    assert extension.calls("pause") == [[]]
    assert extension.calls("setVolume") == [[0.5]]
    assert extension.calls("setShuffle") == [[True]]


async def test_seek_uses_milliseconds(server: SpotifyServer, extension: Extension) -> None:
    extension.require_protocol(1)

    await server.seek(61000)
    await server.seek(500)

    assert extension.calls("PlayerAPI.seekTo") == [[61000], [500]]


async def test_play_uri_and_failures(server: SpotifyServer, extension: Extension) -> None:
    extension.require_protocol(1)

    await server.play_uri("https://open.spotify.com/track/0laYHRpNTS6i8FXdupHkJ4")
    assert extension.calls("playUri") == [["spotify:track:0laYHRpNTS6i8FXdupHkJ4"]]

    with pytest.raises(RequestFailedError) as exc_info:
        await server.play_uri("spotify:track:unavailable")
    assert exc_info.value.code == "command_failed"


async def test_invalid_parameters_are_rejected(server: SpotifyServer, extension: Extension) -> None:
    extension.require_protocol(1)

    with pytest.raises(RequestFailedError) as exc_info:
        await server.play_uri("https://example.com/not-spotify")
    assert exc_info.value.code == "invalid_params"


async def test_mute_restores_the_previous_volume(
    server: SpotifyServer, extension: Extension
) -> None:
    extension.require_protocol(1)

    await server.set_mute(True)
    await server.set_mute(False)

    assert extension.calls("setVolume") == [[0], [0.42]]


async def test_song_change_and_buffering_events(
    server: SpotifyServer, extension: Extension
) -> None:
    extension.require_protocol(1)
    names: list[str] = []
    server.on_state_changed(lambda state: names.append(state.event_name))

    await extension.command("buffering on")
    await asyncio.sleep(0.5)
    names.clear()

    await extension.command("songchange")
    await extension.wait_for(lambda: names == ["SongChanged"])
    await extension.command("buffering off")
    await extension.wait_for(lambda: len(names) >= 2)
    await asyncio.sleep(0.5)

    assert names == ["SongChanged", "BufferingChanged"]


async def test_wrong_api_key_is_rejected(server: SpotifyServer) -> None:
    ext = Extension()
    await ext.start(_url(server), api_key="wrong-key")
    try:
        await ext.wait_for(lambda: any(e["type"] == "sent" for e in ext.events))
        await asyncio.sleep(0.5)
        assert not server.is_connected
    finally:
        await ext.stop()


async def test_unauthorized_requests_get_no_key() -> None:
    """The extension must not send its key to a server that does not know it."""
    received: list[dict[str, Any]] = []

    async def fake_server(ws) -> None:
        await ws.recv()  # InitialState
        await ws.send(json.dumps({"requestName": "Ping", "requestId": "r1", "token": "wrong"}))
        with contextlib.suppress(ConnectionClosed):
            async for raw in ws:
                message = json.loads(raw)
                if message.get("eventName") == "Response":
                    received.append(message)

    ext = Extension()
    async with serve(fake_server, "127.0.0.1", 0) as raw_server:
        port = raw_server.sockets[0].getsockname()[1]
        await ext.start(f"ws://127.0.0.1:{port}")
        try:
            await ext.wait_for(lambda: bool(received))
        finally:
            await ext.stop()

    # Extensions before 0.3.2 echoed their key here; protocol 1 implies the fix.
    ext.require_protocol(1)
    response = received[0]
    assert response["success"] is False
    assert "token" not in response
    assert response["code"] == "unauthorized"
