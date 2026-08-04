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
        # Events
        @server.on_song_changed
        def callback(state: PlayerState):
            track = state.track
            if track:
                print("New song is playing:", track.title)
                print("Artist/s:", ", ".join(artist.name for artist in track.artists))

        # Wildcard listener triggering on every state update
        @server.on_state_changed
        def on_state_update(state: PlayerState):
            print(
                f"[{state.event_name}] Playing: {state.is_playing}"
                f" | Vol: {state.volume}% | Pos: {state.position_seconds:.1f}s"
            )

        # Wait until Spicetify client connects
        await server.wait_for_connection()

        # Playback State
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
