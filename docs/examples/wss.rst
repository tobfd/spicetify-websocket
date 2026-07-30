WSS (WebSocket Secure)
======================

You can encrypt WebSocket communication using SSL/TLS for **Secure WebSockets (wss://)**.

How It Works:

- **Direct SSL/TLS (Local / LAN):** Pass ``certfile`` and ``keyfile`` paths (or a custom :class:`ssl.SSLContext`) to :class:`~spicetify.SpotifyServer`. The server will automatically use the ``wss://`` scheme.
- **Reverse Proxy (VPS / Nginx):** When deploying behind a proxy like Nginx or Caddy, SSL is terminated at the proxy level. Python runs on unencrypted ``ws://`` locally, while Nginx handles public ``wss://`` traffic.
- You can freely combine WSS encryption with ``api_key`` authentication in any setup.

.. note::
   - For setting up local self-signed certificates with SAN, see the :doc:`/guides/local_wss` guide.
   - For production VPS deployment with Nginx and Let's Encrypt, see the :doc:`/guides/vps_deployment` guide.

.. literalinclude:: ../../examples/wss.py
   :language: python
