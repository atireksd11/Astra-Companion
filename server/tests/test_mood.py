"""Feature 11: coarse mood cue. The default tests never load the ONNX file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import (  # noqa: E402
    AntispoofConfig,
    CadenceConfig,
    DenoiseConfig,
    FocusConfig,
    MoodConfig,
    ProfileConfig,
    PronunciationConfig,
    SttConfig,
    load_config,
    normalize_steps,
)
from core.config_validate import (  # noqa: E402
    validate_implemented_steps,
    validate_step_contract,
)
from core.mood import (  # noqa: E402
    MOOD_LABELS,
    RAW_LABELS,
    blend_distribution,
    client_view,
    hello_status,
    map_label,
    note_from_logits,
    score_mood,
)
from core.pipeline import Pipeline  # noqa: E402
from core.speech_profile import ema, empty_profile  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.cadence import make_cadence_step  # noqa: E402
from steps.mood import make_mood_step  # noqa: E402
from steps.pronunciation import make_pronunciation_step  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402

WEIGHTS = ROOT / "models" / "speech_emotion_int8.onnx"
RATE = 16000

_OFF = (
    DenoiseConfig(enabled=False),
    FocusConfig(enabled=False),
    SttConfig(enabled=False),
    CadenceConfig(enabled=False),
    PronunciationConfig(enabled=False),
    AntispoofConfig(enabled=False),
)


def _peak(index: int) -> np.ndarray:
    logits = np.full(len(RAW_LABELS), -4.0, dtype=np.float64)
    logits[index] = 8.0
    return logits


def _happy_logits() -> np.ndarray:
    return _label_logits("HAP")


def _label_logits(raw: str) -> np.ndarray:
    probs = np.full(len(RAW_LABELS), 0.05 / 7.0, dtype=np.float64)
    probs[RAW_LABELS.index(raw)] = 0.95
    return np.log(probs)


def _pcm(seconds: float) -> bytes:
    n = int(seconds * RATE)
    return np.zeros(n, dtype="<i2").tobytes()


def _store(tmp_path: Path) -> ProfileStore:
    store = ProfileStore(tmp_path / "mood.db")
    doc = empty_profile("spk_owner")
    doc["is_owner"] = True
    store.put(doc)
    return store


def _step(store: ProfileStore, cfg: MoodConfig | None = None, *, focus: bool = True):
    focus_cfg = FocusConfig(
        enabled=focus,
        lock_owner=True,
        owner_speaker_id="spk_owner",
    )
    return make_mood_step(cfg or MoodConfig(), store, focus_cfg, ProfileConfig())


def _turn(seconds: float = 1.0, action: str | None = "allow") -> Turn:
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(seconds))
    if action is not None:
        turn.notes["antispoof"] = {"action": action}
    return turn


def test_label_map_keeps_five_and_drops_disgust_and_fear() -> None:
    cfg = MoodConfig()
    expect = {
        "ANG": "angry",
        "HAP": "happy",
        "SAD": "sad",
        "NEU": "neutral",
        "SUR": "surprised",
        "CAL": "neutral",
    }
    for raw, label in expect.items():
        note = note_from_logits(_peak(RAW_LABELS.index(raw)), cfg)
        assert note["label"] == label
        assert note["raw_label"] == raw
        assert note["confidence"] >= 0.70
    for raw in ("DIS", "FEA"):
        note = note_from_logits(_peak(RAW_LABELS.index(raw)), cfg)
        assert note["label"] is None
        assert note["raw_label"] == raw
        assert note["confidence"] >= 0.70


def test_low_confidence_or_margin_nulls_label_and_skips_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    calls = {"n": 0}

    def flat(_samples, _cfg):
        calls["n"] += 1
        return np.zeros(len(RAW_LABELS), dtype=np.float64)

    monkeypatch.setattr("core.mood._logits_for", flat)
    turn = _turn()
    _step(store)(turn)
    note = turn.notes["mood"]
    assert note["label"] is None
    assert note["confidence"] < 0.70
    assert turn.error is None
    assert store.get("spk_owner")["mood"]["samples"] == 0

    # Confidence can clear a lowered floor while the softmax gap stays under 0.15.
    # At the 0.70 floor the gap is already at least 0.40, so this uses the config gates.
    tight = np.full(len(RAW_LABELS), 0.005, dtype=np.float64)
    tight[RAW_LABELS.index("HAP")] = 0.55
    tight[RAW_LABELS.index("NEU")] = 0.42

    def close(_samples, _cfg):
        return np.log(tight)

    monkeypatch.setattr("core.mood._logits_for", close)
    cfg = MoodConfig(min_confidence=0.50, min_margin=0.15)
    turn = _turn()
    _step(store, cfg)(turn)
    assert turn.notes["mood"]["label"] is None
    assert turn.notes["mood"]["confidence"] >= 0.50
    assert store.get("spk_owner")["mood"]["samples"] == 0
    assert calls["n"] == 1


def test_missing_weights_are_unavailable_without_error_or_profile_write(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    cfg = MoodConfig(weights="models/no-such-speech-emotion.onnx")
    turn = _turn()
    _step(store, cfg)(turn)
    note = turn.notes["mood"]
    assert note["backend"] == "unavailable"
    assert note["label"] is None
    assert note["confidence"] == 0
    assert note["raw_label"] is None
    assert turn.error is None
    assert store.get("spk_owner")["mood"]["samples"] == 0
    json.dumps(note)


def test_soft_antispoof_does_not_write_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    turn = _turn(action="soft")
    _step(store)(turn)
    note = turn.notes["mood"]
    assert note["label"] == "happy"
    assert note["confidence"] >= 0.90
    assert turn.error is None
    saved = store.get("spk_owner")
    assert saved is not None
    assert saved["mood"]["samples"] == 0
    assert saved["mood"]["distribution"]["happy"] == 0.2


def test_allow_owner_moves_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    before = store.get("spk_owner")
    assert before is not None
    turn = _turn(action="allow")
    _step(store)(turn)
    got = store.get("spk_owner")
    assert got is not None
    dist = got["mood"]["distribution"]
    assert dist["happy"] > 0.2
    assert abs(sum(dist.values()) - 1.0) < 1e-6
    assert got["mood"]["last_label"] == "happy"
    assert got["mood"]["last_confidence"] >= 0.70
    assert got["mood"]["samples"] == 1
    assert set(dist) == set(MOOD_LABELS)
    assert got["cadence"] == before["cadence"]
    assert got["pronunciation"] == before["pronunciation"]
    assert got["match"] == before["match"]
    assert got["is_owner"] is True


def test_hard_spoof_stops_pipeline_before_later_step() -> None:
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(2.0))

    def antispoof_step(current: Turn) -> None:
        current.notes["antispoof"] = {"action": "hard"}
        current.error = "spoof_suspected"

    def mood_step(current: Turn) -> None:
        current.notes["mood_ran"] = True

    Pipeline([antispoof_step, mood_step], step_timeout_s=5).run(turn)
    assert turn.error == "spoof_suspected"
    assert "mood_ran" not in turn.notes


def test_clip_under_0_8s_is_too_short_and_does_not_write(tmp_path: Path) -> None:
    store = _store(tmp_path)
    turn = _turn(seconds=0.5)
    _step(store, MoodConfig(weights="models/no-such-speech-emotion.onnx"))(turn)
    note = turn.notes["mood"]
    assert note["backend"] == "too_short"
    assert note["label"] is None
    assert note["confidence"] == 0
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_normalize_steps_puts_mood_after_stt_and_before_cadence() -> None:
    steps, _warns = normalize_steps(
        ["echo"],
        *_OFF[:2],
        SttConfig(enabled=True),
        CadenceConfig(enabled=True),
        *_OFF[4:],
        MoodConfig(enabled=True),
    )
    assert steps.index("stt") < steps.index("mood") < steps.index("cadence")
    assert steps.index("cadence") < steps.index("echo")
    scrambled, _scrambled_warns = normalize_steps(
        ["mood", "cadence", "stt", "echo"],
        *_OFF[:2],
        SttConfig(enabled=True),
        CadenceConfig(enabled=True),
        *_OFF[4:],
        MoodConfig(enabled=True),
    )
    assert scrambled.index("stt") < scrambled.index("mood") < scrambled.index("cadence")
    validate_step_contract(["stt", "mood", "cadence", "echo"])
    validate_implemented_steps(["stt", "mood", "echo"])
    with pytest.raises(ValueError, match="must run after"):
        validate_step_contract(["mood", "stt", "echo"])


def test_disabled_mood_is_not_auto_inserted() -> None:
    steps, warns = normalize_steps(["stt", "cadence", "echo"], *_OFF, MoodConfig(enabled=False))
    assert "mood" not in steps
    assert not any("mood" in w for w in warns)


def test_notes_are_json_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    note = score_mood(_pcm(1.0), RATE, MoodConfig(weights="models/no-such-speech-emotion.onnx"))
    json.dumps(note)
    assert set(note) == {"label", "confidence", "backend", "raw_label"}
    for value in note.values():
        assert not isinstance(value, (bytes, bytearray, memoryview, np.ndarray, np.generic))
    short = score_mood(_pcm(0.2), RATE, MoodConfig())
    json.dumps(short)
    assert short["backend"] == "too_short"


def test_empty_profile_starts_uniform() -> None:
    doc = empty_profile("spk_new")
    dist = doc["mood"]["distribution"]
    assert dist == {name: 0.2 for name in MOOD_LABELS}
    assert doc["mood"]["last_label"] is None
    assert doc["mood"]["last_confidence"] == 0
    assert doc["mood"]["samples"] == 0


@pytest.mark.skipif(not WEIGHTS.is_file(), reason="speech emotion weights not present")
def test_optional_onnx_noise_does_not_throw() -> None:
    rng = np.random.default_rng(0)
    pcm = (rng.standard_normal(RATE) * 3000).astype("<i2").tobytes()
    note = score_mood(pcm, RATE, MoodConfig())
    assert note["label"] is None or note["label"] in MOOD_LABELS
    assert not str(note["backend"]).startswith("wav2vec2_ser_int8_error")
    json.dumps(note)
    for value in note.values():
        assert not isinstance(value, (bytes, bytearray, memoryview, np.ndarray, np.generic))


def test_map_label_gates_calm_and_drops_disgust_and_fear() -> None:
    assert map_label("CAL", 0.80, 0.14, 0.70, 0.15) is None
    assert map_label("CAL", 0.80, 0.15, 0.70, 0.15) == "neutral"
    assert map_label("CAL", 0.69, 0.50, 0.70, 0.15) is None
    assert map_label("DIS", 0.99, 0.90, 0.70, 0.15) is None
    assert map_label("FEA", 0.99, 0.90, 0.70, 0.15) is None
    assert map_label("HAP", 0.70, 0.15, 0.70, 0.15) == "happy"
    assert map_label("HAP", 0.70, 0.149, 0.70, 0.15) is None
    assert map_label("SUR", 0.91, 0.40, 0.70, 0.15) == "surprised"


def test_blend_keeps_a_zero_and_sums_to_one() -> None:
    # speech_profile.ema() treats 0 as unset and would replace it with the new value.
    assert ema(0.0, 1.0, 0.1) == 1.0
    prior = {
        "happy": 0.25,
        "sad": 0.25,
        "angry": 0.0,
        "neutral": 0.25,
        "surprised": 0.25,
    }
    out = blend_distribution(prior, "angry", 0.1)
    assert out["angry"] == pytest.approx(0.1)
    assert out["happy"] == pytest.approx(0.225)
    assert abs(sum(out.values()) - 1.0) < 1e-6
    # A partial prior must not be filled with 0.2 per missing class (that sum exceeds 1).
    partial = blend_distribution({"happy": 1.0}, "sad", 0.1)
    assert set(partial) == set(MOOD_LABELS)
    assert partial["sad"] == pytest.approx(0.28)
    assert partial["happy"] == pytest.approx(0.18)
    assert abs(sum(partial.values()) - 1.0) < 1e-6


def test_zero_mass_in_profile_is_not_wiped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _label_logits("ANG"))
    store = _store(tmp_path)
    doc = store.get("spk_owner")
    assert doc is not None
    doc["mood"]["distribution"] = {
        "happy": 0.25,
        "sad": 0.25,
        "angry": 0.0,
        "neutral": 0.25,
        "surprised": 0.25,
    }
    store.put(doc)
    _step(store)(_turn())
    got = store.get("spk_owner")
    assert got is not None
    dist = got["mood"]["distribution"]
    assert dist["angry"] == pytest.approx(0.1)
    assert dist["angry"] != 1.0
    assert abs(sum(dist.values()) - 1.0) < 1e-6
    assert got["mood"]["samples"] == 1
    json.dumps(got["mood"])


def test_focus_off_scores_but_does_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    turn = _turn()
    _step(store, focus=False)(turn)
    assert turn.notes["mood"]["label"] == "happy"
    assert turn.error is None
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_non_owner_and_low_snr_and_barge_do_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    guest = empty_profile("spk_guest")
    guest["is_owner"] = False
    store.put(guest)
    focus = FocusConfig(enabled=True, lock_owner=True, owner_speaker_id="spk_owner")
    step = make_mood_step(MoodConfig(), store, focus, ProfileConfig())

    guest_turn = _turn()
    guest_turn.notes["meta"] = {"speaker_id": "spk_guest", "label": "angry", "mood": "sad"}
    step(guest_turn)
    assert guest_turn.notes["mood"]["label"] == "happy"
    assert store.get("spk_guest")["mood"]["samples"] == 0
    assert store.get("spk_owner")["mood"]["samples"] == 0

    noisy = _turn()
    noisy.notes["noise_after"] = {"snr_db": 1.0}
    step(noisy)
    assert store.get("spk_owner")["mood"]["samples"] == 0

    barged = _turn()
    barged.notes["barged"] = True
    step(barged)
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_missing_antispoof_may_write_and_hard_may_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    open_turn = _turn(action=None)
    assert "antispoof" not in open_turn.notes
    _step(store)(open_turn)
    assert store.get("spk_owner")["mood"]["samples"] == 1

    hard = _turn(action="hard")
    _step(store)(hard)
    assert hard.notes["mood"]["label"] == "happy"
    assert store.get("spk_owner")["mood"]["samples"] == 1


def test_calm_updates_neutral_and_fear_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _label_logits("CAL"))
    store = _store(tmp_path)
    _step(store)(_turn())
    saved = store.get("spk_owner")
    assert saved is not None
    assert saved["mood"]["last_label"] == "neutral"
    assert saved["mood"]["distribution"]["neutral"] > 0.2
    assert saved["mood"]["samples"] == 1

    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _label_logits("FEA"))
    fear = _turn()
    _step(store)(fear)
    assert fear.notes["mood"]["label"] is None
    assert fear.notes["mood"]["raw_label"] == "FEA"
    again = store.get("spk_owner")
    assert again is not None
    assert again["mood"]["samples"] == 1
    assert again["mood"]["last_label"] == "neutral"


def test_short_clip_does_not_call_the_net_and_ignores_a_planted_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def boom(_samples, _cfg):
        calls["n"] += 1
        raise AssertionError("net ran")

    monkeypatch.setattr("core.mood._logits_for", boom)
    store = _store(tmp_path)
    turn = _turn(seconds=0.5)
    turn.notes["mood"] = {"label": "happy", "confidence": 0.99, "backend": "client", "raw_label": "HAP"}
    turn.pcm_pre_denoise = _pcm(3.0)
    _step(store)(turn)
    assert calls["n"] == 0
    assert turn.notes["mood"]["backend"] == "too_short"
    assert turn.notes["mood"]["label"] is None
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_analysis_audio_is_capped_and_ignores_pre_denoise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, int] = {}

    def grab(samples, _cfg):
        seen["n"] = int(samples.shape[0])
        return _happy_logits()

    monkeypatch.setattr("core.mood._logits_for", grab)
    score_mood(_pcm(7.5), RATE, MoodConfig())
    assert seen["n"] == 96000

    turn = Turn(rate_hz=RATE)
    turn.pcm_pre_denoise = _pcm(3.0)
    turn.pcm_in = bytearray(_pcm(2.0))
    turn.notes["antispoof"] = {"action": "allow"}
    note = score_mood(turn.pcm_for_analysis or bytes(turn.pcm_in), RATE, MoodConfig())
    assert seen["n"] == 32000
    assert note["label"] == "happy"

    mono = np.frombuffer(_pcm(1.0), dtype="<i2")
    stereo = np.empty(mono.size * 2, dtype="<i2")
    stereo[0::2] = mono
    stereo[1::2] = mono
    turn.pcm_for_analysis = stereo.tobytes()
    turn.pcm_pre_denoise = _pcm(4.0)
    turn.notes["channels"] = 2
    from steps.mood import _analysis_pcm

    scored = score_mood(_analysis_pcm(turn), RATE, MoodConfig())
    assert seen["n"] == RATE
    assert scored["label"] == "happy"
    assert len(turn.pcm_pre_denoise) != len(_analysis_pcm(turn))


def test_scorer_and_profile_failures_stay_off_turn_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(_samples, _cfg):
        raise RuntimeError("ort blew up")

    monkeypatch.setattr("core.mood._logits_for", explode)
    store = _store(tmp_path)
    turn = _turn()
    Pipeline([_step(store)], step_timeout_s=5).run(turn)
    assert turn.error is None
    assert turn.notes["mood"]["label"] is None
    assert turn.notes["mood"]["backend"] == "wav2vec2_ser_int8_error: RuntimeError"
    assert store.get("spk_owner")["mood"]["samples"] == 0
    json.dumps(turn.notes["mood"])

    def raise_score(*_args, **_kwargs):
        raise RuntimeError("scorer")

    monkeypatch.setattr("steps.mood.score_mood", raise_score)
    turn = _turn()
    Pipeline([_step(store)], step_timeout_s=5).run(turn)
    assert turn.error is None
    assert "wav2vec2_ser_int8_error" in turn.notes["mood"]["backend"]
    assert store.get("spk_owner")["mood"]["samples"] == 0

    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    monkeypatch.setattr("steps.mood.score_mood", score_mood)

    def boom_put(_doc):
        raise RuntimeError("disk")

    monkeypatch.setattr(store, "put", boom_put)
    turn = _turn()
    Pipeline([_step(store)], step_timeout_s=5).run(turn)
    assert turn.error is None
    assert turn.notes["mood"]["label"] == "happy"
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_later_profile_steps_do_not_clobber_mood(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    focus = FocusConfig(enabled=True, lock_owner=True, owner_speaker_id="spk_owner")
    profile = ProfileConfig()
    mood = make_mood_step(MoodConfig(), store, focus, profile)
    cadence = make_cadence_step(CadenceConfig(enabled=True), profile, store, focus)
    pron = make_pronunciation_step(
        PronunciationConfig(enabled=True, aligner="none"),
        profile,
        store,
        focus,
    )
    turn = _turn(seconds=1.2)
    Pipeline([mood, cadence, pron], step_timeout_s=5).run(turn)
    got = store.get("spk_owner")
    assert got is not None
    assert turn.error is None
    assert got["mood"]["samples"] == 1
    assert got["mood"]["last_label"] == "happy"
    assert got["mood"]["distribution"]["happy"] > 0.2
    assert abs(sum(got["mood"]["distribution"].values()) - 1.0) < 1e-6
    assert got["cadence"]["utterances"] == 1
    assert got["is_owner"] is True


def test_hello_ready_is_false_when_the_file_is_missing(tmp_path: Path) -> None:
    missing = hello_status(MoodConfig(weights="models/no-such-speech-emotion.onnx"))
    assert missing["enabled"] is True
    assert missing["backend"] == "wav2vec2_ser_int8"
    assert missing["ready"] is False
    present = tmp_path / "speech_emotion_int8.onnx"
    present.write_bytes(b"not-a-model")
    found = hello_status(MoodConfig(weights=str(present), enabled=False))
    assert found["ready"] is True
    assert found["enabled"] is False
    if WEIGHTS.is_file():
        assert hello_status(MoodConfig())["ready"] is True
    text = (ROOT / "bridge.py").read_text(encoding="utf-8")
    assert "mood_hello_status(self.cfg.mood)" in text
    assert 'body["mood"]' in text


def test_load_config_rejects_mood_before_stt(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "steps": ["mood", "cadence", "stt", "echo"],
                "stt": {"enabled": True},
                "mood": {"enabled": True},
                "cadence": {"enabled": True},
                "denoise": {"enabled": False},
                "focus": {"enabled": False},
                "pronunciation": {"enabled": False},
                "antispoof": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match='step "mood" must run after "stt"'):
        load_config(bad)

    ok = tmp_path / "ok.json"
    ok.write_text(
        json.dumps(
            {
                "steps": ["stt", "mood", "cadence", "echo"],
                "stt": {"enabled": True},
                "mood": {"enabled": True},
                "cadence": {"enabled": True},
                "denoise": {"enabled": False},
                "focus": {"enabled": False},
                "pronunciation": {"enabled": False},
                "antispoof": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(ok)
    assert cfg.steps.index("stt") < cfg.steps.index("mood") < cfg.steps.index("cadence")


def test_laptop_prints_mood_when_done_has_it(capsys: pytest.CaptureFixture[str]) -> None:
    from tools.laptop_voice import _print_turn_summary

    _print_turn_summary(
        {
            "transcript": "hello",
            "mood": {"label": "sad", "confidence": 0.91, "backend": "wav2vec2_ser_int8"},
        }
    )
    first = capsys.readouterr().out
    assert "Mood: sad (0.91)" in first
    _print_turn_summary(
        {"mood": {"label": None, "confidence": 0, "backend": "too_short", "raw_label": None}}
    )
    second = capsys.readouterr().out
    assert "Mood: uncertain" in second
    _print_turn_summary(
        {"mood": {"label": "furious", "confidence": 0.99, "backend": "client", "raw_label": "ANG"}}
    )
    third = capsys.readouterr().out
    assert "Mood: uncertain" in third
    assert "furious" not in third


def test_cap_cannot_be_disabled_or_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, int] = {}

    def grab(samples, _cfg):
        seen["n"] = int(samples.shape[0])
        return _happy_logits()

    monkeypatch.setattr("core.mood._logits_for", grab)
    for cap in (0, 30, float("nan"), float("inf")):
        score_mood(_pcm(7.5), RATE, MoodConfig(max_seconds=cap))
        assert seen["n"] == 96000

    def boom(_samples, _cfg):
        raise AssertionError("net ran")

    monkeypatch.setattr("core.mood._logits_for", boom)
    note = score_mood(_pcm(2.0), RATE, MoodConfig(max_seconds=0.2))
    assert note["backend"] == "too_short"
    assert note["label"] is None
    json.dumps(note, allow_nan=False)


def test_nonfinite_floors_do_not_label_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    assert map_label("HAP", 0.95, 0.40, float("nan"), 0.15) is None
    assert map_label("HAP", 0.95, 0.40, 0.70, float("-inf")) is None
    assert map_label("HAP", float("nan"), 0.40, 0.70, 0.15) is None
    assert map_label("HAP", 0.95, 0.40, False, 0.15) is None
    for cfg in (
        MoodConfig(min_confidence=float("nan")),
        MoodConfig(min_margin=float("-inf")),
        MoodConfig(min_confidence=False),  # type: ignore[arg-type]
    ):
        turn = _turn()
        _step(store, cfg)(turn)
        assert turn.notes["mood"]["label"] is None
        assert turn.error is None
        json.dumps(turn.notes["mood"], allow_nan=False)
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_bad_blend_and_antispoof_shape_do_not_corrupt_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    store = _store(tmp_path)
    _step(store, MoodConfig(ema_alpha=2))(_turn())
    saved = store.get("spk_owner")
    assert saved is not None
    assert saved["mood"]["samples"] == 0
    assert saved["mood"]["distribution"]["happy"] == 0.2
    assert min(saved["mood"]["distribution"].values()) >= 0

    doc = store.get("spk_owner")
    assert doc is not None
    doc["mood"]["samples"] = -4
    store.put(doc)
    _step(store)(_turn())
    got = store.get("spk_owner")
    assert got is not None
    assert got["mood"]["samples"] == 1
    assert got["mood"]["distribution"]["happy"] > 0.2

    spoofed = _turn(action=None)
    spoofed.notes["antispoof"] = "allow"
    _step(store)(spoofed)
    assert spoofed.notes["mood"]["label"] == "happy"
    assert store.get("spk_owner")["mood"]["samples"] == 1


def test_inconsistent_raw_label_and_nan_learn_gates_do_not_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)

    def disagree(_pcm, _rate, cfg):
        return {
            "label": "angry",
            "confidence": 0.99,
            "backend": cfg.backend,
            "raw_label": "DIS",
            "pcm": _pcm,
        }

    monkeypatch.setattr("steps.mood.score_mood", disagree)
    turn = _turn()
    _step(store)(turn)
    assert turn.notes["mood"]["label"] is None
    assert turn.error is None
    assert "pcm" not in turn.notes["mood"]
    json.dumps(turn.notes["mood"], allow_nan=False)
    assert store.get("spk_owner")["mood"]["samples"] == 0

    monkeypatch.setattr("core.mood._logits_for", lambda _s, _c: _happy_logits())
    monkeypatch.setattr("steps.mood.score_mood", score_mood)
    nan_trim = _turn()
    nan_trim.notes["segment"] = {"trim_s": float("nan")}
    _step(store)(nan_trim)
    assert nan_trim.notes["mood"]["label"] == "happy"
    assert store.get("spk_owner")["mood"]["samples"] == 0

    nan_snr = _turn()
    nan_snr.notes["noise_after"] = {"snr_db": float("nan")}
    _step(store)(nan_snr)
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_disabled_step_drops_a_planted_mood_note(tmp_path: Path) -> None:
    store = _store(tmp_path)
    turn = _turn()
    turn.notes["mood"] = {
        "label": "happy",
        "confidence": 0.99,
        "backend": "client",
        "raw_label": "HAP",
    }
    focus = FocusConfig(enabled=True, lock_owner=True, owner_speaker_id="spk_owner")
    make_mood_step(MoodConfig(enabled=False), store, focus, ProfileConfig())(turn)
    assert "mood" not in turn.notes
    assert store.get("spk_owner")["mood"]["samples"] == 0


def test_client_view_is_strict_json_and_hello_survives_a_null_path() -> None:
    dirty = {
        "label": "happy",
        "confidence": np.float32(0.91),
        "backend": "wav2vec2_ser_int8",
        "raw_label": "HAP",
        "pcm": b"\x00\x01",
    }
    view = client_view(dirty)
    assert view is not None
    json.dumps(view, allow_nan=False)
    assert set(view) == {"label", "confidence", "backend", "raw_label"}
    assert view["label"] == "happy"
    assert isinstance(view["confidence"], float)
    assert not isinstance(view["confidence"], np.generic)
    nan_view = client_view(
        {
            "label": "happy",
            "confidence": float("nan"),
            "backend": "wav2vec2_ser_int8",
            "raw_label": "HAP",
        }
    )
    assert nan_view is not None
    assert nan_view["label"] is None
    assert nan_view["confidence"] == 0
    json.dumps(nan_view, allow_nan=False)
    assert client_view("happy") is None
    assert client_view(None) is None
    missing = hello_status(MoodConfig(weights=None))  # type: ignore[arg-type]
    assert missing["ready"] is False
    json.dumps(missing)


def test_duplicate_mood_is_collapsed_and_a_later_stt_fails_load(tmp_path: Path) -> None:
    from core.config_validate import mood_before_cadence

    base = {
        "stt": {"enabled": True},
        "mood": {"enabled": True},
        "cadence": {"enabled": True},
        "denoise": {"enabled": False},
        "focus": {"enabled": False},
        "pronunciation": {"enabled": False},
        "antispoof": {"enabled": False},
    }
    later = tmp_path / "later.json"
    later.write_text(
        json.dumps({"steps": ["stt", "cadence", "mood", "echo"], **base}),
        encoding="utf-8",
    )
    cfg = load_config(later)
    assert cfg.steps.index("stt") < cfg.steps.index("mood") < cfg.steps.index("cadence")

    dup = tmp_path / "dup.json"
    dup.write_text(
        json.dumps({"steps": ["stt", "mood", "cadence", "mood", "echo"], **base}),
        encoding="utf-8",
    )
    collapsed = load_config(dup)
    assert collapsed.steps.count("mood") == 1
    assert collapsed.steps.index("mood") < collapsed.steps.index("cadence")

    interleaved = tmp_path / "interleaved.json"
    interleaved.write_text(
        json.dumps({"steps": ["stt", "mood", "stt", "echo"], **base}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match='step "mood" must run after "stt"'):
        load_config(interleaved)
    with pytest.raises(ValueError, match='step "mood" must run before "cadence"'):
        mood_before_cadence(["stt", "mood", "cadence", "mood", "echo"])
