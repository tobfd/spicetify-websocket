import asyncio
import logging

from spicetify import RepeatMode, SpotifyServer, TrackInfo

logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("spicetify").setLevel(logging.INFO)


async def main():
    async with SpotifyServer() as server:
        # Wait until Spicetify client connects
        await server.wait_for_connection()

        # Playback Controls
        await server.play_url(
            url="https://open.spotify.com/intl-de/track/55pBIZO1cqoldeqpp5WR7H?si=57cde33a1bd34ac9"
        )
        await server.set_volume(percent=75)
        await server.set_repeat(mode=RepeatMode.TRACK)

        # Playback State
        current_track: TrackInfo = await server.get_current_track()
        print(current_track)

        # Events
        @server.on_song_changed
        def callback(track: TrackInfo):
            print("New song is playing:", track.title)
            print("Artist/s:", ", ".join(artist.name for artist in track.artists))

        # Keep the server running to receive events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
