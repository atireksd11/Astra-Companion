"""Allowlisted robot actions attached to done messages."""

from __future__ import annotations

from typing import Any

from core.turn import Turn

ALLOWED = frozenset({"stop_playback", "aim", "set_volume"})

# Same floor as DoaConfig.min_confidence and firmware AudioConfig::kAimMinConfidence.
# Below this the robot ignores the aim action, so planning it only desyncs the two sides.
AIM_MIN_CONFIDENCE = 0.20


def _owner_ok(turn: Turn) -> bool:
    focus = turn.notes.get("focus")
    if isinstance(focus, dict) and focus.get("verified") is True:
        return True
    wake = turn.notes.get("focus_wake")
    if isinstance(wake, dict) and wake.get("verified") is True:
        return True
    return False


def plan_actions(turn: Turn, *, require_owner: bool = True) -> list[dict[str, Any]]:
    """Build action payloads before idempotency filtering."""
    if turn.error:
        return []
    if require_owner and not _owner_ok(turn):
        return []
    anti = turn.notes.get("antispoof")
    if isinstance(anti, dict) and anti.get("action") not in (None, "allow"):
        return []

    out: list[dict[str, Any]] = []
    intent = str(turn.notes.get("intent") or "").casefold()
    if intent == "stop":
        out.append({"name": "stop_playback", "params": {}})

    if "azimuth_deg" in turn.notes:
        try:
            az = float(turn.notes["azimuth_deg"])
            conf = float(turn.notes.get("doa_confidence") or 0)
        except (TypeError, ValueError):
            az = None
            conf = 0.0
        if az is not None and conf >= AIM_MIN_CONFIDENCE:
            out.append(
                {
                    "name": "aim",
                    "params": {"azimuth_deg": round(az, 2), "confidence": round(conf, 3)},
                }
            )

    vol = turn.notes.get("volume")
    if isinstance(vol, dict) and vol.get("firmware_vol") is not None:
        try:
            fv = float(vol["firmware_vol"])
        except (TypeError, ValueError):
            fv = None
        if fv is not None:
            out.append({"name": "set_volume", "params": {"firmware_vol": round(fv, 3)}})

    return [a for a in out if a.get("name") in ALLOWED]


def with_ids(turn: Turn, actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for action in actions:
        name = str(action.get("name") or "")
        if name not in ALLOWED:
            continue
        tagged.append(
            {
                "id": f"{turn.id}:{name}",
                "name": name,
                "params": action.get("params") if isinstance(action.get("params"), dict) else {},
            }
        )
    return tagged
