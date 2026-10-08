"""End-to-end tests for connection handling, using a real server and real clients."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator

import pytest
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from spicetify import NotConnectedError, SpotifyServer
from spicetify.server import SPOTIFY_DESKTOP_ORIGIN

API_KEY = "test-secret-key"


def _url(server: SpotifyServer) -> str:
    assert server.server is not None
    port = server.server.sockets[0].getsockname()[1]
    return f"ws://127.0.0.1:{port}"


def _initial_state(token: str | None = None) -> str:
    message: dict = {"eventName": "InitialState", "payload": {"isPlaying": False}}
    if token is not None:
        message["token"] = token
    return json.dumps(message)


async def _answer_requests(ws: ClientConnection, token: str | None = None) -> None:
    """Behave like the Spicetify extension: answer every request successfully."""
    async for raw in ws:
        request = json.loads(raw)
        response = {
            "eventName": "Response",
            "requestId": request["requestId"],
            "success": True,
            "payload": {},
        }
        if token is not None:
            response["token"] = token
        await ws.send(json.dumps(response))


async def _connect_client(server: SpotifyServer, token: str | None = None) -> ClientConnection:
    """Connect a client that authenticates like the extension does."""
    ws = await connect(_url(server))
    await ws.send(_initial_state(token))
    return ws


async def _wait_until(condition, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        if loop.time() > deadline:
            raise AssertionError("Condition was not met in time")
        await asyncio.sleep(0.01)


@pytest.fixture
async def server() -> AsyncIterator[SpotifyServer]:
    async with SpotifyServer(port=0, api_key=API_KEY, auth_timeout=0.5) as srv:
        yield srv


@pytest.fixture
async def open_server() -> AsyncIterator[SpotifyServer]:
    async with SpotifyServer(port=0, auth_timeout=0.5) as srv:
        yield srv


async def test_api_key_is_never_sent_to_unauthenticated_clients(server: SpotifyServer):
    """A client that has not authenticated must not receive commands or the API key."""
    legit = await _connect_client(server, API_KEY)
    responder = asyncio.create_task(_answer_requests(legit, API_KEY))
    await server.wait_for_connection(timeout=2)

    async with connect(_url(server)) as intruder:
        await asyncio.sleep(0.05)
        await server.play()
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(intruder.recv(), timeout=0.2)

    assert server.websocket is not None
    responder.cancel()
    await legit.close()


async def test_client_with_wrong_token_never_becomes_active(server: SpotifyServer):
    async with connect(_url(server)) as ws:
        await ws.send(_initial_state("wrong-key"))
        await asyncio.sleep(0.1)
        assert not server.is_connected
        with pytest.raises(NotConnectedError):
            await server.play()


async def test_silent_client_is_closed_after_auth_timeout(server: SpotifyServer):
    async with connect(_url(server)) as ws:
        with pytest.raises(ConnectionClosed) as exc_info:
            await asyncio.wait_for(ws.recv(), timeout=2)
    assert exc_info.value.rcvd is not None
    assert exc_info.value.rcvd.code == 1008


async def test_new_client_replaces_and_closes_previous(server: SpotifyServer):
    first = await _connect_client(server, API_KEY)
    await server.wait_for_connection(timeout=2)
    first_conn = server.websocket

    second = await _connect_client(server, API_KEY)
    await _wait_until(lambda: server.websocket is not first_conn)
    responder = asyncio.create_task(_answer_requests(second, API_KEY))

    with pytest.raises(ConnectionClosed):
        await asyncio.wait_for(first.recv(), timeout=2)

    await server.play()
    assert server.is_connected
    responder.cancel()
    await second.close()


async def test_closing_old_connection_keeps_new_one_active(open_server: SpotifyServer):
    """Regression test: an old connection closing must not clear the new active one."""
    old = await _connect_client(open_server)
    await open_server.wait_for_connection(timeout=2)
    new = await _connect_client(open_server)
    # Wait until the replaced connection has been closed by the server.
    await _wait_until(lambda: not open_server._background_tasks)
    responder = asyncio.create_task(_answer_requests(new))

    await old.close()
    await asyncio.sleep(0.1)

    assert open_server.is_connected
    await open_server.play()
    responder.cancel()
    await new.close()


@pytest.mark.parametrize(
    "bad_message",
    [
        "[]",
        '"text"',
        "null",
        "{not json",
        json.dumps(
            {
                "eventName": "SongChanged",
                "payload": {
                    "playerData": {
                        "item": {"uri": "spotify:track:1", "artists": [{"name": None, "uri": "x"}]}
                    }
                },
            }
        ),
    ],
)
async def test_malformed_messages_do_not_close_the_connection(
    open_server: SpotifyServer, bad_message: str
):
    received = []
    open_server.on_state_changed(received.append)

    ws = await _connect_client(open_server)
    await open_server.wait_for_connection(timeout=2)
    received.clear()

    await ws.send(bad_message)
    await ws.send(json.dumps({"eventName": "SongChanged", "payload": {}}))
    await _wait_until(lambda: len(received) >= 1)

    assert open_server.is_connected
    await ws.close()


async def test_pending_request_fails_fast_when_client_disconnects(open_server: SpotifyServer):
    ws = await _connect_client(open_server)
    await open_server.wait_for_connection(timeout=2)

    loop = asyncio.get_running_loop()
    started = loop.time()
    request = asyncio.create_task(open_server.get_volume())
    await asyncio.sleep(0.05)
    await ws.close()

    with pytest.raises(NotConnectedError):
        await request
    assert loop.time() - started < 1.0
    assert open_server._pending_requests == {}


async def test_abrupt_disconnect_is_handled_quietly(
    open_server: SpotifyServer, caplog: pytest.LogCaptureFixture
):
    """A connection reset by the client must not produce an ERROR log with traceback."""
    caplog.set_level(logging.DEBUG)
    ws = await _connect_client(open_server)
    await open_server.wait_for_connection(timeout=2)

    ws.transport.abort()
    await _wait_until(lambda: not open_server.is_connected)

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors == []


async def test_connect_and_disconnect_hooks(server: SpotifyServer):
    events: list[str] = []
    server.on_connect(lambda: events.append("connect"))

    @server.on_disconnect
    async def on_disconnect() -> None:
        events.append("disconnect")

    first = await _connect_client(server, API_KEY)
    await server.wait_for_connection(timeout=2)
    second = await _connect_client(server, API_KEY)
    await asyncio.sleep(0.1)
    assert events == ["connect"]  # a replacement is not a disconnect

    await second.close()
    await _wait_until(lambda: "disconnect" in events)
    assert events == ["connect", "disconnect"]
    await first.close()


async def test_disallowed_origin_is_rejected():
    async with SpotifyServer(port=0, allowed_origins=[SPOTIFY_DESKTOP_ORIGIN]) as srv:
        with pytest.raises(InvalidStatus):
            await connect(_url(srv), origin="https://evil.example")

        async with connect(_url(srv), origin=SPOTIFY_DESKTOP_ORIGIN) as ws:
            await ws.send(_initial_state())
            await srv.wait_for_connection(timeout=2)
            assert srv.is_connected


async def test_stop_fails_pending_requests_and_disconnects(open_server: SpotifyServer):
    ws = await _connect_client(open_server)
    await open_server.wait_for_connection(timeout=2)
    request = asyncio.create_task(open_server.ping())
    await asyncio.sleep(0.05)

    await open_server.stop()

    with pytest.raises(NotConnectedError):
        await request
    assert not open_server.is_connected
    await ws.close()
