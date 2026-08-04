import asyncio
import inspect
import json
import logging
import ssl
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from typing_extensions import Self
from websockets.asyncio.server import Server, ServerConnection, serve

from .exceptions import (
    NotConnectedError,
    RequestTimeoutError,
    SpicetifyError,
    UnauthorizedError,
)
from .models import (
    PlayerState,
    RepeatMode,
    TrackInfo,
    _BaseRequest,
    _ForcePreviousSongRequest,
    _GetCurrentTrackRequest,
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
    _SetMuteRequest,
    _SetRepeatRequest,
    _SetShuffleRequest,
    _SetVolumeRequest,
    _TogglePlayRequest,
)

logger = logging.getLogger(__name__)


class SpotifyServer:
    """WebSocket server for controlling Spotify via Spicetify.

    The server starts a WebSocket listener, waits for a Spicetify client to
    connect, and exposes convenience methods for playback control and state
    queries.

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
        websocket: Active WebSocket connection, if any.
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
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key
        self.ssl_context = ssl_context
        self.certfile = certfile
        self.keyfile = keyfile

        self.websocket: ServerConnection | None = None
        self.server: Server | None = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._connected_event = asyncio.Event()
        self._event_callbacks: dict[str, list[Callable]] = {}
        self._background_tasks: set[asyncio.Task[Any]] = set()

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

    def on_ping(self, func: Callable[[datetime], Any]) -> Callable[[datetime], Any]:
        """Register a callback for the ``Ping`` heartbeat event.

        Args:
            func: Callback function receiving a :class:`datetime` object in UTC.

        Returns:
            The original callback, unchanged.
        """
        return self.on("Ping")(func)

    # --- Event Dispatch ---

    async def _dispatch_event(self, event_name: str, payload: dict[str, Any]) -> None:
        """Dispatch an incoming event to all registered callbacks.

        Args:
            event_name: Name of the received event.
            payload: Event payload received from Spicetify.
        """
        key = event_name.lower()
        specific_callbacks = self._event_callbacks.get(key, [])

        wildcard_callbacks = [] if key == "ping" else self._event_callbacks.get("*", [])

        all_callbacks = specific_callbacks + [
            cb for cb in wildcard_callbacks if cb not in specific_callbacks
        ]
        if not all_callbacks:
            return

        parsed_data = self._parse_event_payload(event_name, payload)

        for callback in all_callbacks:
            # noinspection broad-exception
            try:
                if inspect.iscoroutinefunction(callback):
                    task = asyncio.create_task(callback(parsed_data))
                    self._background_tasks.add(task)
                    task.add_done_callback(self._background_tasks.discard)
                else:
                    callback(parsed_data)
            except Exception:
                logger.exception("Error executing the event callback for %s", event_name)

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
            ts = payload.get("timestamp")
            if isinstance(ts, (int, float)):
                return datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
            return payload

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
        """Wait for a Spicetify client connection.

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

    # --- Server Lifecycle ---

    async def _send_command(self, request: _BaseRequest, timeout: float = 5.0) -> dict:
        """Send a command request to Spicetify and wait for its response.

        Args:
            request: The request object to send.
            timeout: Maximum time to wait for a response. Defaults to ``5.0``.

        Returns:
            The response data from Spicetify.

        Raises:
            NotConnectedError: If no active WebSocket connection exists.
            RequestTimeoutError: If the response doesn't arrive within timeout.
            UnauthorizedError: If the API key token is invalid or missing.
            SpicetifyError: If Spicetify responds with an error status.
        """
        if not self.websocket:
            raise NotConnectedError()

        if self.api_key is not None:
            request.token = self.api_key

        loop = asyncio.get_running_loop()
        future = loop.create_future()

        self._pending_requests[request.requestId] = future

        json_data = request.model_dump_json(exclude_none=True)
        logger.debug("Send: %s", json_data)
        await self.websocket.send(json_data)

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

        self.server = await serve(self._handler, self.host, self.port, ssl=ssl_ctx)
        scheme = "wss" if ssl_ctx else "ws"
        logger.info("Server started on %s://%s:%d", scheme, self.host, self.port)

    async def stop(self) -> None:
        """Stop the WebSocket server and close any active connection."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("WebSocket connection closed.")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Server has stopped.")

    # --- WebSocket Message Handling ---

    async def _handler(self, websocket: ServerConnection) -> None:
        """Handle incoming WebSocket messages and resolve pending requests.

        Args:
            websocket: The WebSocket connection from a client.
        """
        self.websocket = websocket
        self._connected_event.set()
        logger.info("Connection established with %s.", websocket.remote_address[0])
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    event_name = data.get("eventName")
                    request_id = data.get("requestId")
                    incoming_token = data.get("token")

                    if self.api_key is not None and incoming_token != self.api_key:
                        logger.warning(
                            "Dropped incoming message due to invalid or missing API key token."
                        )
                        continue

                    if (
                        event_name == "Response"
                        and request_id
                        and request_id in self._pending_requests
                    ):
                        future = self._pending_requests.pop(request_id)
                        if not future.done():
                            if data.get("success") is False:
                                raw_msg = (
                                    data.get("error")
                                    or data.get("message")
                                    or "Unknown Spicetify error"
                                )
                                msg = str(raw_msg)

                                is_auth_error = any(
                                    term in msg.lower()
                                    for term in (
                                        "unauthorized",
                                        "token",
                                        "api key",
                                        "forbidden",
                                        "denied",
                                    )
                                )

                                if is_auth_error:
                                    future.set_exception(
                                        UnauthorizedError(f"Request failed: {msg}")
                                    )
                                else:
                                    future.set_exception(SpicetifyError(f"Request failed: {msg}"))
                            else:
                                future.set_result(data)
                            logger.debug(
                                "Received response for requestId: %s, Data: %s",
                                request_id,
                                data,
                            )
                        continue

                    if event_name:
                        logger.debug("Event received: %s: %s", event_name, data.get("payload"))
                        await self._dispatch_event(event_name, data.get("payload", {}))

                    else:
                        logger.debug("Received message without eventName or requestId: %s", data)
                except json.JSONDecodeError:
                    logger.error("JSON parsing error: %s", message)
        finally:
            self.websocket = None
            self._connected_event.clear()
            logger.info("Connection lost.")

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

    async def get_current_track(self) -> TrackInfo:
        """Get the current track information from Spicetify.

        Returns:
            A ``TrackInfo`` object containing details about the current track.

        Raises:
            NotConnectedError: If not connected to Spicetify.
            RequestTimeoutError: If Spicetify doesn't respond in time.
            UnauthorizedError: If the API key token is invalid or missing.
        """
        response = await self._send_command(_GetCurrentTrackRequest())
        return TrackInfo.from_payload(response.get("payload", {}))
