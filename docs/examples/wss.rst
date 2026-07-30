WSS (WebSocket Secure)
======================

You can encrypt the WebSocket communication using SSL/TLS certificates for **Secure WebSockets (wss://)**.

How It Works:

- Pass ``certfile`` and ``keyfile`` paths (or a custom :class:`ssl.SSLContext`) to :class:`~spicetify.server.SpotifyServer`.
- The server will automatically start using the ``wss://`` scheme instead of ``ws://``.
- You can freely combine WSS encryption with ``api_key`` authentication.

.. hint::
   When using self-signed certificates locally, ensure the certificate is trusted by your system/browser store or configured with a SAN (Subject Alternative Name) for ``127.0.0.1`` / ``localhost``.

.. literalinclude:: ../../examples/wss.py
   :language: python
