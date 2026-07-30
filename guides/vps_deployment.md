For production deployments on a public Virtual Private Server (VPS), the recommended approach is using **Nginx as a Reverse Proxy** with **Let's Encrypt SSL certificates**.

In this architecture, Nginx handles public SSL/TLS termination (`wss://`) on Port 443 and forwards the decrypted traffic locally to your Python server (`ws://127.0.0.1:9090`).

---

## Step 1: Run the Python Server on VPS

Your Python server runs locally on `127.0.0.1:9090` without SSL files (`certfile`/`keyfile` are **not** needed because Nginx handles SSL):

```python
import asyncio
from spicetify import SpotifyServer

async def main():
    # Runs locally unencrypted; Nginx handles public WSS encryption
    async with SpotifyServer(
        host="127.0.0.1",
        port=9090,
        api_key="your-secret-key",
    ) as server:
        print("Python server listening locally on ws://127.0.0.1:9090")
        await server.wait_for_connection()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 2: Configure Nginx Reverse Proxy

Create an Nginx configuration file named after your domain (e.g., `/etc/nginx/sites-available/your-domain.com`):

```bash
sudo nano /etc/nginx/sites-available/your-domain.com
```

Add the following configuration (replace `your-domain.com` with your actual domain):

```nginx
server {
    server_name your-domain.com;

    location / {
        # Reject non-WebSocket requests (e.g., web scanners/bots) directly at Nginx level
        if ($http_upgrade !~* "websocket") {
            return 426 "Upgrade Required";
        }

        proxy_pass http://127.0.0.1:9090;

        # WebSocket Upgrade Headers
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;

        # Keep connection alive
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }
}
```

Enable the configuration and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/your-domain.com /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

---

## Step 3: Install Certbot & Obtain SSL Certificate

Install Certbot and the Nginx plugin on Ubuntu/Debian:

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
```

Obtain a free Let's Encrypt SSL certificate for your domain:

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot will automatically update your Nginx configuration to enable SSL on Port 443.

---

## Step 4: Configure Spicetify Extension

In Spotify, set the WebSocket URL in the Spicetify Extension settings (omit the port number, as Port 443 is default for `wss://`):

```text
wss://your-domain.com
```

Restart Spotify. The extension will connect seamlessly through Nginx to your VPS!
