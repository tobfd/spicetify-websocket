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
