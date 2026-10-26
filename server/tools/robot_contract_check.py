#!/usr/bin/env python3
"""Print sample bridge `done` JSON with robot actions for firmware devs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.done_contract import (  # noqa: E402
    ACTION_ID_FORMAT,
    plan_done_actions,
    sample_done_json,
)
from core.turn import Turn  # noqa: E402


def _demo_turn() -> Turn:
    turn = Turn()
    turn.id = "demo-turn-001"
    turn.notes["focus"] = {"verified": True}
    turn.notes["intent"] = "stop"
    turn.notes["azimuth_deg"] = 42.5
    turn.notes["doa_confidence"] = 0.72
    turn.notes["volume"] = {"firmware_vol": 0.41}
    return turn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent JSON (default: compact one line)",
    )
    args = parser.parse_args()

    turn = _demo_turn()
    payload = sample_done_json(turn, require_owner=True)
    planned = plan_done_actions(turn, require_owner=True)

    print(f"# action id format: {ACTION_ID_FORMAT}")
    for action in planned:
        print(f"#   {action['id']} -> {action['name']}")

    indent = 2 if args.pretty else None
    # Keep insertion order. sort_keys puts "actions" before "type", and the
    # firmware only treats a frame as done when it starts with {"type":"done".
    print(json.dumps(payload, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
