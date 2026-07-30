"""Example demonstrating API key authentication with Spicetify WebSocket."""

import asyncio
from datetime import datetime

from spicetify import SpotifyServer, TrackInfo, UnauthorizedError


async def main():
    # Pass the api_key parameter to enforce token authentication
    async with SpotifyServer(api_key="your-secret-api-key") as server:
        print("Server started on ws://127.0.0.1:9090 with API Key protection.")

        @server.on_song_changed
        def on_song(track: TrackInfo):
            print(f"🎵 Now playing: {track.title} by {', '.join(a.name for a in track.artists)}")

        @server.on_ping
        def on_ping(ping_time: datetime):
            print(f"💓 Heartbeat at: {ping_time.strftime('%H:%M:%S UTC')}")

        print("⏳ Waiting for Spicetify client to connect...")
        await server.wait_for_connection()
        print("✅ Spicetify client connected successfully!")

        try:
            latency = await server.ping()
            print(f"⚡ Latency to Spicetify: {latency:.2f} ms")
        except UnauthorizedError:
            print("❌ Authentication failed: Invalid API Key token!")
            return

        # Keep server running to receive push events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
