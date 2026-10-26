from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from store.memory import total_speech_seconds_saved
    db_path = ROOT / "astra.db"
    if not db_path.is_file():
        print("no astra.db yet")
        return
    with sqlite3.connect(db_path) as conn:
        cost = conn.execute("SELECT day, usd FROM daily_cost ORDER BY day DESC LIMIT 1").fetchone()
        rows = conn.execute(
            "SELECT id, audio_in_bytes, timings_json, cost_usd, error, notes_json "
            "FROM turns ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    print("daily_cost:", cost)
    print("trim_saved_s:", round(total_speech_seconds_saved(db_path), 2))
    for row in rows:
        tid, ain, timings_json, cost_usd, err, notes_json = row
        timings = json.loads(timings_json) if timings_json else {}
        slow = max(timings.values()) if timings else 0
        notes = json.loads(notes_json) if notes_json else {}
        az = notes.get("azimuth_deg")
        doa = f" az={az}°" if az is not None else ""
        ch = notes.get("channels", 1)
        den = notes.get("denoise") or {}
        dn = ""
        if den:
            dn = f" denoise={den.get('backend')} snr={den.get('snr_after_db')}dB"
        print(
            f"  {tid} ch={ch} in={ain}B{doa}{dn} cost=${cost_usd:.4f} "
            f"err={err} slowest_ms={slow:.1f}"
        )


if __name__ == "__main__":
    main()
