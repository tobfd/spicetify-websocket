Main Example
============

This example demonstrates how to set up the :class:`~spicetify.server.SpotifyServer`, listen for real-time playback events, and issue playback control commands.

.. note::
   Make sure the Spotify desktop client and the **spicetify-connect-api** extension are running before starting the server.

Key Features Demonstrated:

- Registering event handlers with decorators like :meth:`~spicetify.SpotifyServer.on_song_changed`.
- Waiting for a client connection using :meth:`~spicetify.SpotifyServer.wait_for_connection`.
- Checking connection latency with :meth:`~spicetify.SpotifyServer.ping`.
- Controlling playback state (play, volume, repeat mode).

.. literalinclude:: ../../examples/run_server.py
   :language: python
