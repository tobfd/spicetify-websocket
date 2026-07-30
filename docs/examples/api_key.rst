API Key Authentication
======================

You can secure the communication between your Python application and Spicetify by setting an **API Key token**.

How It Works:

- Pass the ``api_key`` parameter when initializing :class:`~spicetify.server.SpotifyServer`.
- All outgoing commands will automatically inject this token into the request.
- Elicited or push events with a missing or invalid token will be dropped, and unauthorized requests will raise an :class:`~spicetify.exceptions.UnauthorizedError`.

.. note::
   Ensure that the exact same API Key token is configured in the **spicetify-connect-api** extension settings within Spotify.

.. literalinclude:: ../../examples/api_key.py
   :language: python
