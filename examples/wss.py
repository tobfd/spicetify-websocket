"""Example demonstrating Secure WebSockets (WSS / SSL/TLS) with Spicetify WebSocket."""

import asyncio
from datetime import datetime

from spicetify import PlayerState, SpotifyServer


async def main():
    # Pass certfile and keyfile paths to enable WSS (wss://)
    # You can also combine this with api_key="your-secret-key" if desired
    async with SpotifyServer(
        certfile="cert.pem",
        keyfile="key.pem",
        # api_key="optional-secret-key",
    ) as server:
        print("Server started on wss://127.0.0.1:9090 (SSL/TLS encrypted).")

        @server.on_song_changed
        def on_song(state: PlayerState):
            track = state.track
            if track:
                print(f"Now playing: {track.title}")

        @server.on_ping
        def on_ping(ping_time: datetime):
            print(f"Heartbeat at: {ping_time.strftime('%H:%M:%S UTC')}")

        print("Waiting for encrypted WSS connection from Spicetify...")
        await server.wait_for_connection()
        print("Secure WSS connection established!")

        latency = await server.ping()
        print(f"Encrypted ping latency: {latency:.2f} ms")

        # Keep server running to receive push events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
