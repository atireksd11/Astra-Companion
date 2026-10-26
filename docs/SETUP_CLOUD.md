# Cloud / VPS hosting (Phase 5)

Laptop mode stays the default. Use this when you want the bridge always on.

## Health check

When `health.enabled` is true, HTTP listens on **websocket port + 1** (default off to avoid port clashes in tests):

- `GET http://127.0.0.1:8766/health` → `{"ok":true,"service":"astra-bridge",...}`

## Auth

Set `ASTRA_AUTH_TOKEN` in the environment (or `security` in config). Clients must send the same value in `hello`:

```json
{"type":"hello","proto":1,"token":"your-secret","fw":"0.1"}
```

Copy the token into `firmware/include/secrets.h` as `BRIDGE_TOKEN`.

## Docker

```powershell
cd server
docker build -t astra-bridge .
docker run --rm -p 8765:8765 -p 8766:8766 -v astra-data:/data `
  -e GROQ_API_KEY=... -e ASTRA_BIND_ALL=1 astra-bridge
```

## TLS (robot)

Set `BRIDGE_USE_TLS 1` in `secrets.h` and terminate TLS on a reverse proxy (Caddy or Cloudflare Tunnel) in front of the bridge, **or** use `wss://` to a host that presents a valid certificate. The ESP32 WebSockets client uses `beginSSL` when TLS is enabled.

## Vision (optional)

Enable in `config.json`:

```json
"vision": { "enabled": true, "provider": "groq", "max_bytes": 400000 }
```

Send a JPEG before `start`:

```json
{"type":"image","mime":"image/jpeg","image_b64":"..."}
```

The caption is injected into the LLM context on the next utterance.

## Database

SQLite file `astra.db` is fine for one user. For a managed DB later, implement `store/repository.py` against Postgres or Turso and keep the same turn/memory semantics.
