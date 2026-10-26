"""Bridge `done` message robot-action contract (shared with firmware tests)."""

from __future__ import annotations

import json
from typing import Any, Callable

from core.robot_actions import plan_actions, with_ids
from core.turn import Turn

# Each action id is `{turn_id}:{action_name}` (one name per turn).
ACTION_ID_FORMAT = "{turn_id}:{action_name}"

# ESP32 copies inbound JSON into this buffer (see firmware/src/net.cpp).
FIRMWARE_INBOUND_TEXT = 8192


def action_id(turn_id: str, action_name: str) -> str:
    return f"{turn_id}:{action_name}"


def plan_done_actions(turn: Turn, *, require_owner: bool = True) -> list[dict[str, Any]]:
    return with_ids(turn, plan_actions(turn, require_owner=require_owner))


ClaimFn = Callable[[str, str, str], bool]


def filter_claimed_actions(
    turn: Turn,
    actions: list[dict[str, Any]],
    claim: ClaimFn,
) -> list[dict[str, Any]]:
    """Mirror bridge idempotency: only actions that win claim() are sent."""
    out: list[dict[str, Any]] = []
    for action in actions:
        aid = str(action.get("id") or "")
        name = str(action.get("name") or "")
        if claim(aid, turn.id, name):
            out.append(action)
    return out


def build_done_payload(
    turn: Turn,
    *,
    actions: list[dict[str, Any]] | None = None,
    include_aim_legacy: bool = True,
) -> dict[str, Any]:
    """Minimal `done` JSON shape the ESP32 cares about (plus turn_id)."""
    msg: dict[str, Any] = {"type": "done", "turn_id": turn.id}
    if actions:
        msg["actions"] = actions
    if include_aim_legacy and "azimuth_deg" in turn.notes:
        msg["aim"] = {
            "azimuth_deg": turn.notes["azimuth_deg"],
            "confidence": turn.notes.get("doa_confidence", 0),
        }
    return msg


def sample_done_json(
    turn: Turn,
    *,
    require_owner: bool = True,
    claim_all: bool = True,
) -> dict[str, Any]:
    """Example payload for firmware bring-up (no DB)."""
    planned = plan_done_actions(turn, require_owner=require_owner)
    actions = planned if claim_all else None
    return build_done_payload(turn, actions=actions)


def stitch_done_message(
    turn_id: str,
    *,
    actions: list[dict[str, Any]] | None = None,
    aim: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build full `done` JSON with robot fields before long transcript/reply."""
    msg: dict[str, Any] = {"type": "done", "turn_id": turn_id}
    if actions:
        msg["actions"] = actions
    if aim is not None:
        msg["aim"] = aim
    if body:
        msg.update(body)
    return msg


def robot_critical_prefix(payload: dict[str, Any]) -> dict[str, Any]:
    """Subset the firmware must see even when the full frame is truncated."""
    head: dict[str, Any] = {"type": payload.get("type"), "turn_id": payload.get("turn_id")}
    if "actions" in payload:
        head["actions"] = payload["actions"]
    if "aim" in payload:
        head["aim"] = payload["aim"]
    return head


def prefix_fits_firmware_buffer(
    payload: dict[str, Any],
    *,
    limit: int = FIRMWARE_INBOUND_TEXT,
) -> bool:
    prefix = json.dumps(robot_critical_prefix(payload), separators=(",", ":"))
    return len(prefix.encode("utf-8")) < limit


def actions_before_heavy_fields(payload: dict[str, Any]) -> bool:
    """True when serialized JSON lists actions before transcript/reply."""
    raw = json.dumps(payload, separators=(",", ":"))
    actions_at = raw.find('"actions":')
    if actions_at < 0:
        return True
    for key in ("transcript", "reply"):
        pos = raw.find(f'"{key}":')
        if pos >= 0 and pos < actions_at:
            return False
    return True
