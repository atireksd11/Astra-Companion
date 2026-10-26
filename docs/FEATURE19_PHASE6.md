# Phase 6 — Robot bring-up and E2E contract hardening

Phase 5 defined `done.actions[]` on the bridge and idempotent logging in SQLite. Phase 6 makes the robot actually consume that array and gives you a repeatable bring-up path.

## Delivered

| Area | What |
|------|------|
| Firmware | Lightweight parser for `done.actions[]`: `stop_playback`, `set_volume`, `aim` |
| Compatibility | Top-level `aim`, `type:volume`, string match for `stop_playback`, and `type:stop` unchanged |
| Contract tests | `server/tests/test_phase6.py` plus `core/done_contract.py` helpers |
| CLI sample | `python tools/robot_contract_check.py` prints example `done` JSON |
| Bring-up | [ROBOT_BRINGUP.md](ROBOT_BRINGUP.md) step-by-step for secrets, flash, bridge, voice |
| CI script | `scripts/RUN-PHASE6-TESTS.ps1` |

## Action id format

Each action in `done.actions[]` includes:

```text
"id": "{turn_id}:{action_name}"
```

Allowed `name` values: `stop_playback`, `aim`, `set_volume`. Params match `server/core/robot_actions.py`.

## Verify on laptop

```powershell
cd "C:\The XyZ Plan\Astra Companion\server"
python tools/robot_contract_check.py --pretty
python -m pytest tests/test_phase6.py -q
```

Or from repo root:

```powershell
.\scripts\RUN-PHASE6-TESTS.ps1
```

## Verify on hardware

Follow [ROBOT_BRINGUP.md](ROBOT_BRINGUP.md). After a verified-owner stop intent, serial should show `net: action stop_playback` (and legacy fallback still stops playback if the array is missing).

## Related

- Phase 5 overview: [FEATURE18_PHASE5.md](FEATURE18_PHASE5.md)
- Voice wiring: [VOICE_SETUP.md](VOICE_SETUP.md)
