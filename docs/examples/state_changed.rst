Wildcard State Listener
=======================

This example shows how to use the wildcard :meth:`~spicetify.SpotifyServer.on_state_changed` decorator to receive a full :class:`~spicetify.models.PlayerState` snapshot whenever any playback event occurs in Spotify.

.. literalinclude:: ../../examples/state_changed.py
   :language: python
   :linenos:
