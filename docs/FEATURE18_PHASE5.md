# Phase 5 — Cloud, robot contract, vision (laptop-testable)

## Delivered

| Area | What |
|------|------|
| Health | `GET /health` on port **8766** when WS is **8765** (`health.enabled`) |
| Auth | Existing `hello.token` + `ASTRA_AUTH_TOKEN`; firmware `BRIDGE_TOKEN` |
| Vision | Optional `image` message → `vision` pipeline step → `<vision>` in LLM context |
| Robot actions | `done.actions[]` with idempotent keys in SQLite (`robot_actions` table) |
| Retention | `store_audio_days` purges old `turns` rows at bridge startup |
| Hosting | `server/Dockerfile`, [SETUP_CLOUD.md](SETUP_CLOUD.md) |
| Firmware | Larger JSON buffer, token in hello, optional TLS + heartbeat, `stop_playback` on done |

## Laptop checks

```powershell
curl http://127.0.0.1:8766/health
python -m pytest tests/test_phase5.py -q
```

## Not in this slice

- Postgres/Turso adapter (contract only in `store/repository.py`)
- On-device camera pipeline
- Full JSON action parser on ESP32 (string match for `stop_playback` only)
