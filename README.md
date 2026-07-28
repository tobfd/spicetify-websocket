[![spicetify-websocket](https://github.com/tobfd/spicetify-websocket/blob/master/docs/_static/logo.png?raw=true)](https://github.com/tobfd/spicetify-websocket)

[![PyPI Version](https://img.shields.io/pypi/v/spicetify-websocket?style=for-the-badge&logo=pypi&logoColor=white&color=magenta)](https://pypi.org/project/spicetify-websocket/)
[![GitHub License](https://img.shields.io/github/license/tobfd/spicetify-websocket?style=for-the-badge&logo=github&color=red)](https://github.com/tobfd/spicetify-websocket/blob/master/LICENSE)
[![](https://img.shields.io/badge/python-3.10%2B-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Read the Docs](https://img.shields.io/readthedocs/spicetify-websocket?style=for-the-badge&logo=readthedocs)](https://spicetify-websocket.readthedocs.io/)

An asynchronous Python wrapper and WebSocket server for controlling the Spotify desktop client via [Spicetify](https://spicetify.app/) and the [spicetify-connect-api]([https://github.com/tobfd/spicetify-connect-api) extension.

## ✨ Features

- ⚡ **Real-time Push Events:** Instant updates for song changes, volume, seeking, and playback state.
- 🎮 **Full Playback Control:** Play, pause, skip, seek, volume, repeat, and shuffle.
- 🛠️ **Convenience Decorators:** Easy event listening with syntax like `@server.on_song_changed`.
- 🏷️ **Fully Typed:** Pydantic V2 models (`TrackInfo`, `PlayerState`, `RepeatMode`).
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

## 🚀 Example Usage

```python
import asyncio
from spicetify import RepeatMode, SpotifyServer, TrackInfo


async def main():
    async with SpotifyServer() as server:

        # Events
        @server.on_song_changed
        def callback(track: TrackInfo):
            print("New song is playing:", track.title)
            print("Artist/s:", ", ".join(artist.name for artist in track.artists))

        # Wait until Spicetify client connects
        await server.wait_for_connection()

        # Playback State
        is_playing: bool = await server.get_is_playing()
        print("Is Spotify playing:", is_playing)

        # Playback Controls
        await server.play_url(url="https://open.spotify.com/intl-de/track/55pBIZO1cqoldeqpp5WR7H?si=57cde33a1bd34ac9")
        await server.set_volume(percent=75)
        await server.set_repeat(mode=RepeatMode.TRACK)

        # Keep the server running to receive events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📻 Events Reference

| Event Name | Convenience Decorator | Callback Payload Type | Description |
| :--- | :--- | :--- | :--- |
| `InitialState` | `@server.on_initial_state` | `PlayerState` | Fired immediately when Spicetify connects. |
| `SongChanged` | `@server.on_song_changed` | `TrackInfo` | Fired when a new track starts playing. |
| `PlayPauseChanged` | `@server.on_play_pause_changed` | `PlayerState` | Fired when playback state changes. |
| `VolumeChanged` | `@server.on_volume_changed` | `float` (0–100%) | Fired when volume level changes. |
| `RepeatChanged` | `@server.on_repeat_changed` | `RepeatMode` | Fired when repeat mode changes (OFF, CONTEXT, TRACK). |
| `ShuffleChanged` | `@server.on_shuffle_changed` | `bool` | Fired when shuffle mode is toggled. |
| `SeekChanged` | `@server.on_seek_changed` | `int` (ms) | Fired when timeline position is manually changed. |
---
