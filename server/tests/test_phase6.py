from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.done_contract import (  # noqa: E402
    ACTION_ID_FORMAT,
    FIRMWARE_INBOUND_TEXT,
    action_id,
    actions_before_heavy_fields,
    build_done_payload,
    filter_claimed_actions,
    plan_done_actions,
    prefix_fits_firmware_buffer,
    sample_done_json,
    stitch_done_message,
)
from core.config import DoaConfig  # noqa: E402
from core.robot_actions import AIM_MIN_CONFIDENCE, ALLOWED, plan_actions, with_ids  # noqa: E402
from core.turn import Turn  # noqa: E402
from store.action_log import ActionLog  # noqa: E402


def test_robot_actions_planning_unchanged() -> None:
    turn = Turn()
    turn.notes["intent"] = "stop"
    assert plan_actions(turn, require_owner=True) == []
    turn.notes["focus"] = {"verified": True}
    raw = plan_actions(turn, require_owner=True)
    assert raw[0]["name"] == "stop_playback"
    tagged = with_ids(turn, raw)
    assert tagged[0]["id"] == action_id(turn.id, "stop_playback")
    assert set(ALLOWED) == {"stop_playback", "aim", "set_volume"}


def test_action_id_contract_document() -> None:
    assert ACTION_ID_FORMAT == "{turn_id}:{action_name}"
    assert action_id("abc-123", "aim") == "abc-123:aim"


def test_done_payload_includes_actions_when_claimed(tmp_path: Path) -> None:
    turn = Turn()
    turn.notes["focus"] = {"verified": True}
    turn.notes["intent"] = "stop"
    turn.notes["azimuth_deg"] = 10.0
    turn.notes["doa_confidence"] = 0.5
    planned = plan_done_actions(turn, require_owner=True)
    assert len(planned) >= 2

    log = ActionLog(tmp_path / "phase6.db")

    def claim(aid: str, tid: str, name: str) -> bool:
        return log.claim(aid, turn_id=tid, action_name=name)

    claimed = filter_claimed_actions(turn, planned, claim)
    assert len(claimed) == len(planned)
    payload = build_done_payload(turn, actions=claimed)
    assert payload["type"] == "done"
    assert payload["turn_id"] == turn.id
    assert "actions" in payload
    names = {a["name"] for a in payload["actions"]}
    assert "stop_playback" in names
    assert "aim" in names
    assert payload["aim"]["azimuth_deg"] == 10.0


def test_sample_done_json_serializable() -> None:
    turn = Turn()
    turn.id = "t-sample"
    turn.notes["focus_wake"] = {"verified": True}
    turn.notes["volume"] = {"firmware_vol": 0.33}
    doc = sample_done_json(turn, require_owner=True)
    text = json.dumps(doc)
    parsed = json.loads(text)
    assert parsed["type"] == "done"
    vol_actions = [a for a in parsed.get("actions", []) if a["name"] == "set_volume"]
    assert vol_actions
    assert vol_actions[0]["params"]["firmware_vol"] == 0.33


def test_duplicate_actions_not_in_second_done(tmp_path: Path) -> None:
    turn = Turn()
    turn.notes["focus"] = {"verified": True}
    turn.notes["intent"] = "stop"
    planned = plan_done_actions(turn, require_owner=True)
    log = ActionLog(tmp_path / "dup6.db")

    def claim(aid: str, tid: str, name: str) -> bool:
        return log.claim(aid, turn_id=tid, action_name=name)

    first = filter_claimed_actions(turn, planned, claim)
    second = filter_claimed_actions(turn, planned, claim)
    assert len(first) == 1
    assert second == []


def test_stitch_done_puts_actions_before_reply() -> None:
    turn = Turn()
    turn.notes["focus"] = {"verified": True}
    turn.notes["intent"] = "stop"
    actions = plan_done_actions(turn, require_owner=True)
    payload = stitch_done_message(
        turn.id,
        actions=actions,
        body={
            "transcript": "x" * 400,
            "reply": "y" * 400,
        },
    )
    assert actions_before_heavy_fields(payload)
    assert prefix_fits_firmware_buffer(payload, limit=FIRMWARE_INBOUND_TEXT)


def test_transcript_substring_does_not_fake_actions_key() -> None:
    """Firmware matches `\"actions\":` and `\"name\":\"stop_playback\"` anywhere.

    Those substrings must occur only as real keys. A transcript that quotes
    them has to stay escaped, and it must not be serialized ahead of actions.
    """
    turn = Turn()
    turn.notes["focus"] = {"verified": True}
    turn.notes["intent"] = "stop"
    actions = plan_done_actions(turn, require_owner=True)
    quoted = 'please "name":"stop_playback" and "actions": [1]'
    payload = stitch_done_message(
        turn.id,
        actions=actions,
        body={
            "transcript": quoted,
            "reply": quoted,
        },
    )
    assert actions_before_heavy_fields(payload)
    for raw in (
        json.dumps(payload),
        json.dumps(payload, separators=(",", ":")),
    ):
        assert raw.startswith('{"type":')
        assert raw.find('"actions":') < raw.find('"transcript":')
        assert raw.find('"actions":') < raw.find('"reply":')
        stop_hits = raw.count('"name":"stop_playback"') + raw.count(
            '"name": "stop_playback"'
        )
        assert stop_hits == 1
        assert raw.count('"actions":') == 1


def test_aim_confidence_matches_firmware_floor() -> None:
    """Robot skips aim below 0.20. Planning 0.15 made the bridge send a no-op."""
    assert AIM_MIN_CONFIDENCE == 0.20
    assert DoaConfig.min_confidence == AIM_MIN_CONFIDENCE
    turn = Turn()
    turn.notes["focus"] = {"verified": True}
    turn.notes["azimuth_deg"] = -18.0
    turn.notes["intent"] = "stop"
    turn.notes["doa_confidence"] = 0.15
    assert [a["name"] for a in plan_actions(turn)] == ["stop_playback"]
    turn.notes["doa_confidence"] = 0.199
    assert [a["name"] for a in plan_actions(turn)] == ["stop_playback"]
    turn.notes["doa_confidence"] = 0.20
    planned = plan_actions(turn)
    assert [a["name"] for a in planned] == ["stop_playback", "aim"]
    assert planned[1]["params"]["confidence"] == 0.2
    assert [a["name"] for a in planned].count("aim") == 1


def test_contract_sample_starts_with_type(monkeypatch, capsys) -> None:
    """sort_keys put actions first, so the firmware never saw type done."""
    monkeypatch.setattr(sys, "argv", ["robot_contract_check"])
    from tools.robot_contract_check import main

    assert main() == 0
    body = next(
        line for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    )
    parsed = json.loads(body)
    assert body.startswith('{"type": "done"')
    assert parsed["type"] == "done"
    assert "actions" in parsed
    assert body.find('"type":') < body.find('"actions":')
