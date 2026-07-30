This guide explains how to set up Secure WebSockets (`wss://`) for local development or LAN usage.

Because Spotify (built on Chromium) strictly enforces HTTPS/WSS security, you must create a self-signed SSL certificate with a **Subject Alternative Name (SAN)** and trust it in Windows.

---

## Use Cases

1. **Single Machine (Same PC):** Both Spotify and your Python application run on the same computer using `127.0.0.1` / `localhost`.
2. **Local Network (LAN / Home Server):** Your Python application runs on a Home Server (e.g. IP `192.168.178.200`), and Spotify runs on your main PC.

---

## Step 1: Generate Certificate & Key

Choose one of the following methods to generate `cert.pem` and `key.pem`.

### Option A: Using OpenSSL (Linux / WSL / Ubuntu)

Replace `192.168.178.200` with your actual IP address (or `127.0.0.1` if on the same PC):

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=192.168.178.200" -addext "subjectAltName=IP:192.168.178.200"
```

---

### Option B: Native Windows 11 (without Linux / WSL)

On Windows 11 without WSL, the easiest tool is **[mkcert](https://github.com/FiloSottile/mkcert)**, which automatically creates and installs a local Root CA into your Windows Certificate Store.

1. **Install `mkcert` via Chocolatey or Scoop (Admin PowerShell):**
   ```powershell
   choco install mkcert
   # OR
   scoop install mkcert
   ```

2. **Install local Root CA into Windows:**
   ```powershell
   mkcert -install
   ```

3. **Generate certificates (for LAN IP or localhost):**
   ```powershell
   # For Home Server / LAN:
   mkcert -cert-file cert.pem -key-file key.pem 192.168.178.200

   # OR for local PC development:
   mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1
   ```

*(Note: When using `mkcert`, Step 2 below is handled automatically by `mkcert -install`!)*

---

## Step 2: Trust the Certificate in Windows

If you generated your certificate via **OpenSSL**, you must import `cert.pem` into your local Trusted Root Certification Authorities store so Spotify/Chromium trusts it.

Open **PowerShell as Administrator** and run:

```powershell
Import-Certificate -FilePath "C:\Path\To\cert.pem" -CertStoreLocation Cert:\LocalMachine\Root
```

---

## Step 3: Run the Python Server

Pass `certfile` and `keyfile` to your `SpotifyServer` instance.

> **Note on `host` parameter:**
> - Use `host="0.0.0.0"` if running on a Home Server so other PCs in your LAN can connect.
> - Use default `SpotifyServer()` (or `host="127.0.0.1"`) if Spotify and Python run on the same PC.

```python
import asyncio
from spicetify import SpotifyServer

async def main():
    # Example for Home Server (listening on all interfaces):
    async with SpotifyServer(
        host="0.0.0.0",
        port=9090,
        certfile="cert.pem",
        keyfile="key.pem",
        api_key="your-secret-key",  # Optional
    ) as server:
        print("Server running on wss://192.168.178.200:9090")
        await server.wait_for_connection()
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Step 4: Configure Spicetify Extension

In Spotify, set the WebSocket URL in the Spicetify Extension settings:

```text
wss://192.168.178.200:9090
```
*(Replace with `wss://127.0.0.1:9090` if on the same PC).*

Restart Spotify. The extension will now connect securely via WSS!
