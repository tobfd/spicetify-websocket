import asyncio
import hmac
import inspect
import json
import logging
import ssl
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any

from typing_extensions import Self
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from .exceptions import (
    NotConnectedError,
    RequestFailedError,
    RequestTimeoutError,
    UnauthorizedError,
)
from .models import (
    PlayerState,
    RepeatMode,
    TrackInfo,
    _BaseRequest,
    _ForcePreviousSongRequest,
    _GetCurrentTrackRequest,
    _GetHeartRequest,
    _GetPlayerStateRequest,
    _GetPlayPauseRequest,
    _GetVolumeRequest,
    _NextSongRequest,
    _PauseRequest,
    _PingRequest,
    _PlayRequest,
    _PlayUriRequest,
    _PreviousSongRequest,
    _SeekRequest,
    _SetHeartRequest,
    _SetMuteRequest,
    _SetRepeatRequest,
    _SetShuffleRequest,
    _SetVolumeRequest,
    _ToggleHeartRequest,
    _TogglePlayRequest,
)

logger = logging.getLogger(__name__)

#: Origin sent by the Spotify desktop client (Spicetify runs inside this page).
SPOTIFY_DESKTOP_ORIGIN = "https://xpui.app.spotify.com"

#: Newest version of the extension's message format (PROTOCOL.md) this library knows.
SUPPORTED_PROTOCOL_VERSION = 1

# WebSocket close code used when a client fails to authenticate in time (RFC 6455: 1008).
_CLOSE_POLICY_VIOLATION = 1008


class SpotifyServer:
    """WebSocket server for controlling Spotify via Spicetify.

    The server starts a WebSocket listener, waits for a Spicetify client to
    connect, and exposes convenience methods for playback control and state
    queries.

    A connection only becomes the *active* connection after it has sent its
    first valid message (the extension sends ``InitialState`` right after
    connecting). If an ``api_key`` is configured, that message must carry the
    matching token. Until then the connection receives no commands and never
    sees the API key. Connections that stay silent or unauthorized for
    ``auth_timeout`` seconds are closed. When a new client authenticates, it
    replaces the previous active connection, which is then closed.

    Note:
        This class is asynchronous and is intended to be used as an async
        context manager.

    Attributes:
        host: Hostname to bind the server to.
        port: Port to bind the server to.
        api_key: Optional API key token required for message authorization.
        ssl_context: Custom SSL context for secure WebSocket connections.
        certfile: Path to SSL certificate file for WSS.
        keyfile: Path to SSL private key file for WSS.
        allowed_origins: Optional list of accepted ``Origin`` header values.
        auth_timeout: Seconds a new connection may take to authenticate.
        websocket: Active (authenticated) WebSocket connection, if any.
        server: Running WebSocket server instance, if any.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9090,
        api_key: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
        certfile: str | None = None,
        keyfile: str | None = None,
        allowed_origins: Sequence[str | None] | None = None,
        auth_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self.ssl_context = ssl_context
        self.certfile = certfile
        self.keyfile = keyfile
        self.allowed_origins = list(allowed_origins) if allowed_origins is not None else None
        self.auth_timeout = auth_timeout

        self.websocket: ServerConnection | None = None
        self.server: Server | None = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._connected_event = asyncio.Event()
        self._event_callbacks: dict[str, list[Callable]] = {}
        self._connect_callbacks: list[Callable[[], Any]] = []
        self._disconnect_callbacks: list[Callable[[], Any]] = []
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._client_protocol_version: int | None = None
        self._client_version: str | None = None

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if an authenticated Spicetify client is connected."""
        return self.websocket is not None

    @property
    def client_protocol_version(self) -> int | None:
        """Protocol version of the connected extension.

        ``0`` for extensions that predate protocol versioning (v0.3.x and
        older), ``None`` while no client is connected.
        """
        return self._client_protocol_version if self.is_connected else None

    @property
    def client_version(self) -> str | None:
        """Version of the connected spicetify-connect-api extension, if it reports one."""
        return self._client_version if self.is_connected else None

    # --- Event Registration ---

    def on(self, event_name: str) -> Callable[[Callable[[Any], Any]], Callable[[Any], Any]]:
        """Register a callback for a Spicetify event.

        The decorated callback is invoked whenever the matching event is
        received from the connected Spicetify client. Callback names are
        matched case-insensitively.

        Args:
            event_name: Name of the Spicetify event to subscribe to, or '*' for all state events.

        Returns:
            A decorator that registers the given function as event handler.
        """

        def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
            key = event_name.lower()
            if key not in self._event_callbacks:
                self._event_callbacks[key] = []
            self._event_callbacks[key].append(func)
            return func

        return decorator

    # --- Convenience Event Decorators ---

    def on_state_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a wildcard callback that fires on EVERY state update event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("*")(func)

    def on_initial_state(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``InitialState`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("InitialState")(func)

    def on_song_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``SongChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("SongChanged")(func)

    def on_play_pause_changed(
        self, func: Callable[[PlayerState], Any]
    ) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``PlayPauseChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("PlayPauseChanged")(func)

    def on_volume_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``VolumeChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("VolumeChanged")(func)

    def on_repeat_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``RepeatChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("RepeatChanged")(func)

    def on_shuffle_changed(
        self, func: Callable[[PlayerState], Any]
    ) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``ShuffleChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("ShuffleChanged")(func)

    def on_seek_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``SeekChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("SeekChanged")(func)

    def on_heart_changed(self, func: Callable[[PlayerState], Any]) -> Callable[[PlayerState], Any]:
        """Register a callback for the ``HeartChanged`` event.

        Args:
            func: Callback function receiving a :class:`PlayerState` object.

        Returns:
            The original callback, unchanged.
        """
        return self.on("HeartChanged")(func)

    def on_ping(self, func: Callable[[datetime], Any]) -> Callable[[datetime], Any]:
        """Register a callback for the ``Ping`` heartbeat event.

        Args:
            func: Callback function receiving a :class:`datetime` object in UTC.

        Returns:
            The original callback, unchanged.
        """
        return self.on("Ping")(func)

    # --- Connection Lifecycle Hooks ---

    def on_connect(self, func: Callable[[], Any]) -> Callable[[], Any]:
        """Register a callback fired when a Spicetify client becomes the active connection.

        The callback takes no arguments and may be a regular function or a coroutine.

        Args:
            func: Callback function.

        Returns:
            The original callback, unchanged.
        """
        self._connect_callbacks.append(func)
        return func

    def on_disconnect(self, func: Callable[[], Any]) -> Callable[[], Any]:
        """Register a callback fired when the active Spicetify connection is lost.

        The callback takes no arguments and may be a regular function or a coroutine.
        It is not fired when a connection is replaced by a newer one, because the
        client stays connected in that case.

        Args:
            func: Callback function.

        Returns:
            The original callback, unchanged.
        """
        self._disconnect_callbacks.append(func)
        return func

    # --- Event Dispatch ---

    def _run_callback(self, callback: Callable, args: tuple[Any, ...], label: str) -> None:
        """Run a user callback, scheduling coroutines as background tasks.

        Exceptions raised by the callback are logged and never propagate.

        Args:
            callback: Sync or async callable to execute.
            args: Positional arguments passed to the callback.
            label: Human-readable name used in log messages.
        """
        # noinspection broad-exception
        try:
            if inspect.iscoroutinefunction(callback):

                async def _run_async() -> None:
                    # noinspection broad-exception
                    try:
                        await callback(*args)
                    except Exception:
                        logger.exception("Error executing async callback for %s", label)

                task = asyncio.create_task(_run_async())
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
            else:
                callback(*args)
        except Exception:
            logger.exception("Error executing callback for %s", label)

    async def _dispatch_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Dispatch an incoming event to all registered callbacks.

        Args:
            event_name: Name of the received event.
            payload: Event payload received from Spicetify.
        """
        key = event_name.lower()
        specific_callbacks = self._event_callbacks.get(key, [])

        # Wildcard '*' callbacks only trigger for PlayerState events, NOT for Ping
        wildcard_callbacks = [] if key == "ping" else self._event_callbacks.get("*", [])

        # Avoid duplicate execution if a callback was registered twice
        all_callbacks = specific_callbacks + [
            cb for cb in wildcard_callbacks if cb not in specific_callbacks
        ]
        if not all_callbacks:
            return

        # noinspection broad-exception
        try:
            parsed_data = self._parse_event_payload(event_name, payload)
        except Exception:
            logger.exception("Could not parse payload of event %s", event_name)
            return

        for callback in all_callbacks:
            self._run_callback(callback, (parsed_data,), f"event {event_name}")

    @staticmethod
    def _parse_event_payload(event_name: str, payload: dict[str, Any]) -> Any:
        """Convert a raw event payload into a typed Python value.

        Args:
            event_name: Name of the event that produced the payload.
            payload: Raw payload as received from Spicetify.

        Returns:
            A UTC :class:`datetime` for Ping events, or a :class:`PlayerState`
            object for all other events.
        """
        if event_name.lower() == "ping":
            ts = payload.get("timestamp") if isinstance(payload, dict) else None
            if isinstance(ts, str):
                try:
                    ts = float(ts)
                except ValueError:
                    ts = None
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            return datetime.now(tz=timezone.utc)

        return PlayerState.from_payload(payload, event_name=event_name)

    # --- Async Context Manager ---

    async def __aenter__(self) -> Self:
        """Enter the async context manager.

        Returns:
            The running server instance.
        """
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the async context manager and stop the server."""
        await self.stop()

    # --- Connection Management ---

    async def wait_for_connection(self, timeout: float | None = None) -> None:
        """Wait for an authenticated Spicetify client connection.

        Args:
            timeout: Maximum time to wait in seconds. If ``None``, waits indefinitely.

        Raises:
            NotConnectedError: If timeout expires before connection is established.
        """
        if self.websocket is not None:
            return

        if timeout is None:
            await self._connected_event.wait()
        else:
            try:
                await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning("Connection timeout after %f seconds", timeout)
                raise NotConnectedError("Timeout: Spicetify did not connect in time.") from None

    def _is_authorized(self, data: dict[str, Any]) -> bool:
        """Check the token of an incoming message against the configured API key.

        Uses a constant-time comparison to avoid leaking the key through timing.

        Args:
            data: Decoded incoming message.

        Returns:
            ``True`` if no API key is configured or the token matches.
        """
        if self.api_key is None:
            return True
        token = data.get("token")
        if not isinstance(token, str):
            return False
        return hmac.compare_digest(token.encode(), self.api_key.encode())

    def _fail_pending_requests(self, reason: str) -> None:
        """Fail every pending request immediately instead of letting it time out.

        Args:
            reason: Message for the raised :class:`NotConnectedError`.
        """
        pending = list(self._pending_requests.values())
        self._pending_requests.clear()
        for future in pending:
            if not future.done():
                future.set_exception(NotConnectedError(reason))

    async def _close_quietly(self, websocket: ServerConnection, code: int, reason: str) -> None:
        """Close a connection and swallow any error raised while doing so."""
        # noinspection broad-exception
        try:
            await websocket.close(code=code, reason=reason)
        except Exception:
            logger.debug("Error while closing connection", exc_info=True)

    def _spawn(self, coro: Any) -> None:
        """Run a coroutine in the background and keep a reference to its task."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _activate_connection(self, websocket: ServerConnection) -> None:
        """Make an authenticated connection the active one.

        A previously active connection is replaced and closed. Requests that were
        sent over it can never be answered, so they fail right away.

        Args:
            websocket: The newly authenticated connection.
        """
        previous = self.websocket
        self.websocket = websocket
        self._connected_event.set()

        if previous is not None and previous is not websocket:
            logger.info("A new Spicetify client connected; replacing the previous connection.")
            self._fail_pending_requests("The connection was replaced by a new Spicetify client.")
            self._spawn(self._close_quietly(previous, 1000, "Replaced by a new connection"))
            return

        logger.info("Spicetify client connected from %s.", _remote_host(websocket))
        for callback in self._connect_callbacks:
            self._run_callback(callback, (), "on_connect")

    def _update_client_info(self, payload: Any) -> None:
        """Remember which extension and protocol version the client reported.

        Args:
            payload: Payload of an ``InitialState`` event.
        """
        payload = payload if isinstance(payload, dict) else {}
        version = payload.get("protocolVersion")
        protocol = version if isinstance(version, int) and not isinstance(version, bool) else 0
        extension = payload.get("extensionVersion")
        self._client_version = extension if isinstance(extension, str) else None
        if protocol > SUPPORTED_PROTOCOL_VERSION and protocol != self._client_protocol_version:
            logger.warning(
                "The Spicetify extension uses protocol version %s, but this library only "
                "knows version %s. Update spicetify-websocket to use all features.",
                protocol,
                SUPPORTED_PROTOCOL_VERSION,
            )
        self._client_protocol_version = protocol

    def _deactivate_connection(self, websocket: ServerConnection) -> None:
        """Clear the active connection if (and only if) it is the given one.

        Args:
            websocket: The connection that has been closed.
        """
        if self.websocket is not websocket:
            return
        self.websocket = None
        self._client_protocol_version = None
        self._client_version = None
        self._connected_event.clear()
        self._fail_pending_requests("The connection to Spicetify was lost.")
        logger.info("Spicetify client disconnected.")
        for callback in self._disconnect_callbacks:
            self._run_callback(callback, (), "on_disconnect")

    # --- Server Lifecycle ---

    async def _send_command(self, request: _BaseRequest, timeout: float = 5.0) -> dict:
        """Send a command request to Spicetify and wait for its response.

        Args:
            request: The request object to send.
            timeout: Maximum time to wait for a response. Defaults to ``5.0``.

        Returns:
            The response data from Spicetify.

        Raises:
            NotConnectedError: If no active connection exists or it is lost
                before the response arrives.
            RequestTimeoutError: If the response doesn't arrive within timeout.
            UnauthorizedError: If the API key token is invalid or missing.
            SpicetifyError: If Spicetify responds with an error status.
        """
        websocket = self.websocket
        if websocket is None:
            raise NotConnectedError()

        if self.api_key is not None:
            request.token = self.api_key

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_requests[request.requestId] = future

        json_data = request.model_dump_json(exclude_none=True)
        logger.debug("Send request: %s (%s)", request.requestName, request.requestId)
        try:
            await websocket.send(json_data)
        except ConnectionClosed as err:
            self._pending_requests.pop(request.requestId, None)
            raise NotConnectedError("The connection to Spicetify was lost.") from err

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(request.requestId, None)
            raise RequestTimeoutError(request.requestName, timeout) from None

    async def start(self) -> None:
        """Start the WebSocket server."""
        ssl_ctx = self.ssl_context
        if ssl_ctx is None and self.certfile and self.keyfile:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)

        self.server = await serve(
            self._handler,
            self.host,
            self.port,
            ssl=ssl_ctx,
            origins=self.allowed_origins,
        )
        scheme = "wss" if ssl_ctx else "ws"
        logger.info("Server started on %s://%s:%d", scheme, self.host, self.port)
        if self.api_key is None:
            logger.info("No API key configured; any client that can reach the server can connect.")

    async def stop(self) -> None:
        """Stop the WebSocket server and close any active connection."""
        websocket = self.websocket
        if websocket is not None:
            self._deactivate_connection(websocket)
            await self._close_quietly(websocket, 1001, "Server shutting down")
            logger.info("WebSocket connection closed.")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            logger.info("Server has stopped.")

    # --- WebSocket Message Handling ---

    async def _enforce_auth_timeout(self, websocket: ServerConnection) -> None:
        """Close a connection that did not authenticate within ``auth_timeout``."""
        await asyncio.sleep(self.auth_timeout)
        logger.warning(
            "Closing connection from %s: no valid message within %.0f s.",
            _remote_host(websocket),
            self.auth_timeout,
        )
        await self._close_quietly(websocket, _CLOSE_POLICY_VIOLATION, "Unauthorized")

    async def _handler(self, websocket: ServerConnection) -> None:
        """Handle one client connection from handshake to close.

        Args:
            websocket: The WebSocket connection from a client.
        """
        logger.debug("Incoming connection from %s.", _remote_host(websocket))
        authenticated = False
        warned_unauthorized = False
        auth_timer = asyncio.create_task(self._enforce_auth_timeout(websocket))
        try:
            async for message in websocket:
                data = _decode_message(message)
                if data is None:
                    continue

                if not self._is_authorized(data):
                    if not warned_unauthorized:
                        logger.warning(
                            "Dropped message from %s: invalid or missing API key token.",
                            _remote_host(websocket),
                        )
                        warned_unauthorized = True
                    continue

                if data.get("eventName") == "InitialState":
                    self._update_client_info(data.get("payload"))

                if not authenticated:
                    authenticated = True
                    auth_timer.cancel()
                    self._activate_connection(websocket)

                if self.websocket is not websocket:
                    # This connection has been replaced by a newer one.
                    continue

                # noinspection broad-exception
                try:
                    await self._process_message(data)
                except Exception:
                    logger.exception("Error while processing message from Spicetify")
        except ConnectionClosed as err:
            logger.info("Connection from %s closed unexpectedly: %s", _remote_host(websocket), err)
        finally:
            auth_timer.cancel()
            self._deactivate_connection(websocket)

    async def _process_message(self, data: dict[str, Any]) -> None:
        """Route an authorized message to pending requests or event callbacks.

        Args:
            data: Decoded incoming message.
        """
        event_name = data.get("eventName")
        request_id = data.get("requestId")

        if event_name == "Response" and request_id:
            future = self._pending_requests.pop(request_id, None)
            if future is None or future.done():
                logger.debug("Ignoring response for unknown request %s", request_id)
                return
            if data.get("success") is False:
                msg = str(data.get("error") or data.get("message") or "Unknown Spicetify error")
                code = data.get("code") if isinstance(data.get("code"), str) else None
                # Extensions before protocol version 1 send no code; fall back to the text.
                if code == "unauthorized" or (code is None and _looks_like_auth_error(msg)):
                    future.set_exception(UnauthorizedError(f"Request failed: {msg}"))
                else:
                    future.set_exception(RequestFailedError(f"Request failed: {msg}", code))
            else:
                future.set_result(data)
            logger.debug("Received response for requestId: %s", request_id)
            return

        if isinstance(event_name, str) and event_name:
            payload = data.get("payload")
            logger.debug("Event received: %s", event_name)
            await self._dispatch_event(event_name, payload if isinstance(payload, dict) else {})
        else:
            logger.debug("Received message without eventName: %s", data)

    # --- Active Ping & Commands ---

    async def ping(self) -> float:
        """Send a Ping request to Spotify and measure round-trip latency.

        Returns:
            Round-trip latency in milliseconds.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        start_time = time.perf_counter()
        await self._send_command(_PingRequest())
        end_time = time.perf_counter()
        return (end_time - start_time) * 1000.0

    async def play(self) -> None:
        """Send a command to start playback.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_PlayRequest())

    async def pause(self) -> None:
        """Send a command to pause playback.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_PauseRequest())

    async def next_song(self) -> None:
        """Send a command to play the next song.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_NextSongRequest())

    async def previous_song(self, force: bool = False) -> None:
        """Send a command to play the previous song.

        Args:
            force: If ``True``, ensures the previous song is played.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        if force:
            await self._send_command(_ForcePreviousSongRequest())
        else:
            await self._send_command(_PreviousSongRequest())

    async def set_repeat(self, mode: RepeatMode) -> RepeatMode:
        """Set the repeat mode for playback.

        Args:
            mode: The repeat mode to set (off, context, track).

        Returns:
            The repeat mode that was set.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_SetRepeatRequest(mode=mode))
        return mode

    async def set_shuffle(self, state: bool) -> bool:
        """Enable or disable shuffle mode.

        Args:
            state: ``True`` to enable shuffle, ``False`` to disable.

        Returns:
            The shuffle state that was set.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_SetShuffleRequest(state=state))
        return state

    async def set_mute(self, state: bool) -> bool:
        """Enable or disable mute for playback.

        Args:
            state: ``True`` to mute, ``False`` to unmute.

        Returns:
            The mute state that was set.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_SetMuteRequest(state=state))
        return state

    async def toggle_play(self) -> None:
        """Send a command to toggle playback (play/pause).

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_TogglePlayRequest())

    async def set_volume(self, percent: float) -> float | int:
        """Set Spotify volume level.

        Args:
            percent: Volume level between 0 and 100.

        Returns:
            The volume level that was set.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
            ValueError: If percent is not between 0 and 100.
        """
        if not 0 <= percent <= 100:
            raise ValueError("percent must be between 0 and 100.")
        await self._send_command(_SetVolumeRequest(level=(percent / 100)))
        return percent

    async def play_uri(self, uri: str) -> str:
        """Play a specific Spotify URI.

        Args:
            uri: Spotify URI or URL to play.

        Returns:
            The URI/URL that was played.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_PlayUriRequest(uri=uri))
        return uri

    async def play_url(self, url: str) -> str:
        """Alias for play_uri. Play a specific Spotify URL.

        Args:
            url: Spotify URL to play.

        Returns:
            The URL that was played.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self.play_uri(uri=url)
        return url

    async def seek(self, position: float) -> int | float:
        """Seek to a specific position in the current track.

        Args:
            position: Position in milliseconds to seek to.

        Returns:
            The position that was sought to.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
            ValueError: If position is negative.
        """
        if not position >= 0:
            raise ValueError("position must be greater than or equal to 0.")
        await self._send_command(_SeekRequest(position=position))
        return position

    async def get_heart(self) -> bool:
        """Get the current like/heart status for the active track.

        Returns:
            ``True`` if the track is liked/hearted, ``False`` otherwise.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetHeartRequest())
        return response.get("payload", {}).get("isHearted", False)

    async def set_heart(self, status: bool) -> bool:
        """Set the like/heart status for the current track.

        Args:
            status: ``True`` to like/heart the track, ``False`` to unlike.

        Returns:
            The heart status that was set.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        await self._send_command(_SetHeartRequest(status=status))
        return status

    async def toggle_heart(self) -> bool:
        """Toggle the like/heart status for the current track.

        Returns:
            The new heart status after toggling.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_ToggleHeartRequest())
        return response.get("payload", {}).get("isHearted", False)

    # --- Playback State Queries ---

    async def get_player_state(self) -> PlayerState:
        """Get the current playback state from Spicetify.

        Returns:
            A ``PlayerState`` object containing the current playback state.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetPlayerStateRequest())
        return PlayerState.from_payload(response.get("payload", {}), event_name="GetPlayerState")

    async def get_is_playing(self) -> bool:
        """Get the current play/pause state from Spicetify.

        Returns:
            ``True`` if currently playing, ``False`` if paused.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetPlayPauseRequest())
        return response.get("payload", {}).get("isPlaying", False)

    async def get_volume(self) -> float | int:
        """Get the current volume level from Spicetify.

        Returns:
            The current volume level between ``0`` and ``100``.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetVolumeRequest())
        return response.get("payload", {}).get("level", 0) * 100

    async def get_current_track(self) -> TrackInfo | None:
        """Get the current track information from Spicetify.

        Returns:
            A ``TrackInfo`` object for the current track, or ``None`` if nothing is loaded.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetCurrentTrackRequest())
        payload = response.get("payload")
        track = payload.get("track") if isinstance(payload, dict) else None
        if not isinstance(track, dict) or not track:
            return None
        return TrackInfo.from_payload(track)


# --- Module Helpers ---


def _decode_message(message: str | bytes) -> dict[str, Any] | None:
    """Decode a raw WebSocket message into a JSON object.

    Args:
        message: Raw text or binary frame.

    Returns:
        The decoded object, or ``None`` if the message is not a JSON object.
    """
    try:
        data = json.loads(message)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Dropped message that is not valid JSON.")
        return None
    if not isinstance(data, dict):
        logger.warning("Dropped JSON message that is not an object.")
        return None
    return data


def _looks_like_auth_error(message: str) -> bool:
    """Guess whether a Spicetify error message is about authorization."""
    lowered = message.lower()
    return any(term in lowered for term in ("unauthorized", "api key", "forbidden"))


def _remote_host(websocket: ServerConnection) -> str:
    """Return the remote host of a connection for log messages."""
    address = getattr(websocket, "remote_address", None)
    if isinstance(address, (tuple, list)) and address:
        return str(address[0])
    return "unknown"
