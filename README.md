[![spicetify-websocket](https://github.com/tobfd/spicetify-websocket/blob/master/docs/_static/logo.png?raw=true)](https://github.com/tobfd/spicetify-websocket)

[![PyPI Version](https://img.shields.io/pypi/v/spicetify-websocket?style=for-the-badge&logo=pypi&logoColor=white&color=magenta)](https://pypi.org/project/spicetify-websocket/)
[![GitHub License](https://img.shields.io/github/license/tobfd/spicetify-websocket?style=for-the-badge&logo=github&color=red)](https://github.com/tobfd/spicetify-websocket/blob/master/LICENSE)
[![](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Read the Docs](https://img.shields.io/readthedocs/spicetify-websocket?style=for-the-badge&logo=readthedocs)](https://spicetify-websocket.readthedocs.io/)

An asynchronous Python wrapper and WebSocket server for controlling the Spotify desktop client via [Spicetify](https://spicetify.app/) and the [spicetify-connect-api](https://github.com/tobfd/spicetify-connect-api) extension.

## ✨ Features

- ⚡ **Real-time Push Events:** Instant updates for song changes, volume, seeking, shuffle, repeat, heart/like status, and ping heartbeats.
- 🌐 **Wildcard State Decorator:** Listen to every state update event with a single `@server.on_state_changed` decorator.
- 🎮 **Full Playback Control:** Play, pause, skip, seek, volume, repeat, shuffle, and ping latency checks.
- 🔑 **API Key Security:** Optional token authorization for securing command execution and event streaming.
- 🔒 **Secure WebSockets (WSS):** Built-in SSL/TLS support via `ssl_context` or `certfile`/`keyfile`.
- 🏷️ **Rich & Fully Typed Models:** Complete Pydantic V2 models.
- 🔄 **Async & Non-blocking:** Built on `asyncio` and `websockets` for maximum performance.

---

## ⚙️ Installation

Python 3.10 or higher is required.

```bash
pip install spicetify-websocket
```

---

## 📋 Prerequisites

To use this library, ensure you have:
1. **Spotify Desktop Client** installed.
2. **[Spicetify CLI](https://spicetify.app/)** installed and configured.
3. The **[spicetify-connect-api](https://github.com/tobfd/spicetify-connect-api)** extension enabled in Spicetify.

---

## 📚 Documentation & Guides

Explore the official [documentation](https://spicetify-websocket.readthedocs.io/) for detailed references and setup guides:

- 📖 **[API Reference](https://spicetify-websocket.readthedocs.io/)** – Full documentation for `SpotifyServer`, models, decorators, and exceptions.
- 💡 **[Code Examples](https://spicetify-websocket.readthedocs.io/en/latest/examples/examples.html)** – Runnable scripts for basic usage, API key auth, and WSS encryption.
- 🛠️ **[Deployment Guides](https://spicetify-websocket.readthedocs.io/en/latest/guides/guides.html)** – Step-by-step guides for local WSS setups and production VPS deployment.

---

## 🚀 Example Usage

```python
import asyncio
from spicetify import PlayerState, RepeatMode, SpotifyServer


async def main():
    async with SpotifyServer() as server:
        # Event handler for song changes
        @server.on_song_changed
        def on_song_changed(state: PlayerState):
            track = state.track
            if track:
                print("New song is playing:", track.title)
                print("Artist/s:", ", ".join(artist.name for artist in track.artists))

        # Wait until Spicetify client connects
        await server.wait_for_connection()

        # Playback State Query
        is_playing: bool = await server.get_is_playing()
        print("Is Spotify playing:", is_playing)

        # Playback Controls
        await server.play_url(url="https://open.spotify.com/intl-de/track/55pBIZO1cqoldeqpp5WR7H")
        await server.set_volume(percent=75)
        await server.set_repeat(mode=RepeatMode.TRACK)

        # Keep the server running to receive events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📻 Events Reference

All state-related event handlers receive a comprehensive [`PlayerState`](https://spicetify-websocket.readthedocs.io/) object containing the full player snapshot.

| Event Name | Convenience Decorator | Callback Payload Type | Description |
| :--- | :--- | :--- | :--- |
| `*` (Wildcard) | `@server.on_state_changed` | `PlayerState` | Fired on **every** player state update event. |
| `InitialState` | `@server.on_initial_state` | `PlayerState` | Fired immediately when Spicetify connects. |
| `SongChanged` | `@server.on_song_changed` | `PlayerState` | Fired when a new track starts playing. |
| `PlayPauseChanged` | `@server.on_play_pause_changed` | `PlayerState` | Fired when playback state changes (play/pause). |
| `VolumeChanged` | `@server.on_volume_changed` | `PlayerState` | Fired when volume level changes. |
| `RepeatChanged` | `@server.on_repeat_changed` | `PlayerState` | Fired when repeat mode changes (`OFF`, `CONTEXT`, `TRACK`). |
| `ShuffleChanged` | `@server.on_shuffle_changed` | `PlayerState` | Fired when shuffle mode is toggled. |
| `SeekChanged` | `@server.on_seek_changed` | `PlayerState` | Fired when timeline position is manually changed. |
| `HeartChanged` | `@server.on_heart_changed` | `PlayerState` | Fired when the active track's heart/like status changes. |
| `Ping` | `@server.on_ping` | `datetime` (UTC) | Fired on periodic heartbeat pings from Spicetify. |

### Connection Lifecycle Hooks

| Decorator | Callback Signature | Description |
| :--- | :--- | :--- |
| `@server.on_connect` | `() -> None` | Fired when a Spicetify client becomes the active connection. |
| `@server.on_disconnect` | `() -> None` | Fired when the active connection is lost (not when it is replaced by a newer client). |

`server.is_connected` tells you at any time whether an authenticated client is connected.

---

## 🔐 Connection & Security Model

- **Authentication on the first message:** A new connection becomes active only after it sends its first valid message (the extension sends `InitialState` right after connecting). With an `api_key`, that message must carry the matching token. Until then the connection receives no commands and never sees the key.
- **Silent clients are closed:** Connections that do not authenticate within `auth_timeout` seconds (default `10`) are closed with code `1008`.
- **One active client:** When a new client authenticates, it replaces the previous connection, which is then closed. Pending requests on the old connection fail immediately with `NotConnectedError`.
- **Origin allowlist (recommended):** Pass `allowed_origins=[SPOTIFY_DESKTOP_ORIGIN]` to reject browser pages from other sites (cross-site WebSocket hijacking). Clients that send no `Origin` header (for example Python scripts) are rejected too; add `None` to the list to allow them.
- **Use WSS outside localhost:** The API key travels inside the messages, so use `wss://` (see the guides) whenever the server is reachable from your network.

```python
from spicetify import SPOTIFY_DESKTOP_ORIGIN, SpotifyServer

server = SpotifyServer(
    host="0.0.0.0",
    api_key="a-long-random-secret",
    allowed_origins=[SPOTIFY_DESKTOP_ORIGIN],
    certfile="cert.pem",
    keyfile="key.pem",
)
```
