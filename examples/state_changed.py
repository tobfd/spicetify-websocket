"""Example demonstrating wildcard state listeners with @server.on_state_changed."""

import asyncio

from spicetify import PlayerState, SpotifyServer


async def main():
    async with SpotifyServer() as server:
        # Wildcard listener triggering on EVERY state update event
        @server.on_state_changed
        def on_state_update(state: PlayerState):
            track_title = state.track.title if state.track else "No Track"
            print(
                f"[{state.event_name}] {track_title}"
                f" | Playing: {state.is_playing}"
                f" | Hearted: {state.is_hearted}"
                f" | Vol: {state.volume}%"
                f" | Pos: {state.position_seconds:.1f}s"
            )

        print("Waiting for Spicetify client connection...")
        await server.wait_for_connection()
        print("Spicetify connected! Streaming state updates...")

        # Keep server running to receive events
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
