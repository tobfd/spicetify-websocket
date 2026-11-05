API Key Authentication
======================

You can secure the communication between your Python application and Spicetify by setting an **API Key token**.

How It Works:

- Pass the ``api_key`` parameter when initializing :class:`~spicetify.server.SpotifyServer`.
- All outgoing commands will automatically inject this token into the request.
- A connection only becomes active after its first message carries the matching token. Until then it receives no commands and never sees the key.
- Messages with a missing or invalid token are dropped, and connections that do not authenticate within ``auth_timeout`` seconds are closed.
- If Spicetify rejects a command because of a token mismatch, an :class:`~spicetify.exceptions.UnauthorizedError` is raised.

.. note::
   Ensure that the exact same API Key token is configured in the **spicetify-connect-api** extension settings within Spotify.

.. literalinclude:: ../../examples/api_key.py
   :language: python
