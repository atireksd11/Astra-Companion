from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.antispoof import (  # noqa: E402
    hello_status,
    make_windows,
    playback_for_echo,
    score_raw_pcm16,
    self_echo_corr,
    weights_path,
)
from core.pipeline import Pipeline  # noqa: E402
from core.config import (  # noqa: E402
    AntispoofConfig,
    CadenceConfig,
    DenoiseConfig,
    FocusConfig,
    MoodConfig,
    PronunciationConfig,
    SttConfig,
    load_config,
    normalize_steps,
)
from core.config_validate import validate_step_contract  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.antispoof import make_antispoof_step  # noqa: E402

WEIGHTS = ROOT / "models" / "AASIST-L.pth"
RATE = 16000


def _voiced(seconds: float = 2.0, rate: int = RATE) -> np.ndarray:
    n = int(seconds * rate)
    t = np.arange(n, dtype=np.float32) / rate
    wave = 0.25 * np.sin(2 * np.pi * 180 * t) + 0.12 * np.sin(2 * np.pi * 240 * t)
    return wave.astype(np.float32)


def _pcm(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return (clipped * 32767.0).astype("<i2").tobytes()


def _cfg(**kwargs) -> AntispoofConfig:
    base = dict(enabled=True, weights="models/no-such-AASIST-L.pth")
    base.update(kwargs)
    return AntispoofConfig(**base)


def _fake_infer(score: float, reliable: bool = True):
    def infer(samples, weights, backend):
        return {
            "backend": "aasist_l",
            "spoof_score": score,
            "spoof_score_max": score,
            "n_windows": 1,
            "reliable": reliable,
        }

    return infer


def _run(score: float, playback: bytes | None, reliable: bool = True) -> Turn:
    pcm = _pcm(_voiced(2.0))
    step = make_antispoof_step(_cfg(), lambda: playback)
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(pcm)
    turn.notes["channels"] = 1
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(score, reliable)):
        step(turn)
    return turn


def test_echo_delayed_copy() -> None:
    voiced = _voiced(2.0)
    delay = 1600
    mic = np.concatenate([np.zeros(delay, dtype=np.float32), voiced])
    corr = self_echo_corr(mic, voiced, RATE)
    assert corr is not None and corr > 0.9


def test_echo_inverted_scaled_copy() -> None:
    voiced = _voiced(2.0)
    delay = 800
    mic = np.concatenate([np.zeros(delay, dtype=np.float32), -0.2 * voiced])
    corr = self_echo_corr(mic, voiced, RATE)
    assert corr is not None and corr > 0.9


def test_echo_independent_noise() -> None:
    rng = np.random.default_rng(0)
    mic = rng.standard_normal(RATE * 2).astype(np.float32) * 0.2
    play = rng.standard_normal(RATE * 2).astype(np.float32) * 0.2
    corr = self_echo_corr(mic, play, RATE)
    assert corr is not None and corr < 0.3


def test_echo_empty_or_silent_playback() -> None:
    voiced = _voiced(2.0)
    assert self_echo_corr(voiced, np.zeros(0, dtype=np.float32), RATE) is None
    assert self_echo_corr(voiced, np.zeros(RATE * 2, dtype=np.float32), RATE) is None
    assert self_echo_corr(voiced, voiced[: RATE // 2], RATE) is None


def test_missing_weights_allows_and_still_measures_echo() -> None:
    pcm = _pcm(_voiced(2.0))
    step = make_antispoof_step(_cfg(), lambda: pcm)
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(pcm)
    step(turn)
    note = turn.notes["antispoof"]
    assert note["backend"] == "aasist_l_unavailable"
    assert note["spoof_score"] is None
    assert note["action"] == "allow"
    assert turn.error is None
    assert note["echo_corr"] is not None and note["echo_corr"] > 0.9
    json.dumps(note)


def test_hard_score_with_echo_is_not_hard() -> None:
    pcm = _pcm(_voiced(2.0))
    turn = _run(1.0, pcm)
    assert turn.notes["antispoof"]["action"] == "soft"
    assert turn.error is None
    assert turn.notes["antispoof"]["echo_corr"] > 0.9


def test_hard_score_without_echo_rejects() -> None:
    turn = _run(1.0, None)
    assert turn.notes["antispoof"]["action"] == "hard"
    assert turn.error == "spoof_suspected"
    assert turn.notes["antispoof"]["raise_verify"] == 0


def test_soft_score_raises_verify_without_error() -> None:
    turn = _run(0.85, None)
    note = turn.notes["antispoof"]
    assert note["action"] == "soft"
    assert turn.error is None
    assert note["raise_verify"] > 0


def test_low_score_allows() -> None:
    turn = _run(0.2, None)
    note = turn.notes["antispoof"]
    assert note["action"] == "allow"
    assert turn.error is None
    assert note["raise_verify"] == 0


def test_windows_and_short_clip_unreliable() -> None:
    long = np.zeros(64600 * 3, dtype=np.float32)
    windows = make_windows(long)
    assert len(windows) == 3
    assert all(w.shape == (64600,) for w in windows)
    near = make_windows(np.zeros(64600 + 1000, dtype=np.float32))
    assert len(near) == 1
    short = make_windows(np.zeros(8000, dtype=np.float32))
    assert len(short) == 1 and short[0].shape == (64600,)
    note = score_raw_pcm16(_pcm(np.zeros(8000, dtype=np.float32)), RATE, _cfg(), None)
    assert note["reliable"] is False
    assert note["spoof_score"] is None
    assert note["action"] == "allow"


def test_stereo_copy_does_not_touch_pcm_in() -> None:
    mono = _pcm(_voiced(1.2))
    samples = np.frombuffer(mono, dtype="<i2")
    stereo = np.empty(samples.size * 2, dtype="<i2")
    stereo[0::2] = samples
    stereo[1::2] = samples
    raw = stereo.tobytes()
    step = make_antispoof_step(_cfg(), lambda: None)
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(raw)
    turn.notes["channels"] = 2
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(0.2)):
        step(turn)
    assert bytes(turn.pcm_in) == raw
    assert turn.notes["channels"] == 2
    json.dumps(turn.notes["antispoof"])


def test_normalize_puts_antispoof_before_denoise() -> None:
    steps, _warns = normalize_steps(
        ["denoise", "echo"],
        DenoiseConfig(enabled=True),
        FocusConfig(enabled=False),
        SttConfig(enabled=False),
        CadenceConfig(enabled=False),
        PronunciationConfig(enabled=False),
        AntispoofConfig(enabled=True),
        MoodConfig(enabled=False),
    )
    assert steps.index("antispoof") < steps.index("denoise")


def test_disabled_antispoof_is_not_treated_as_active() -> None:
    steps, warns = normalize_steps(
        ["echo", "antispoof"],
        DenoiseConfig(enabled=False),
        FocusConfig(enabled=False),
        SttConfig(enabled=False),
        CadenceConfig(enabled=False),
        PronunciationConfig(enabled=False),
        AntispoofConfig(enabled=False),
        MoodConfig(enabled=False),
    )
    assert steps == ["echo", "antispoof"]
    assert not warns


def test_contract_rejects_denoise_before_antispoof() -> None:
    with pytest.raises(ValueError, match="must run after"):
        validate_step_contract(["denoise", "antispoof", "echo"])


def test_focus_raise_applies_to_wake_and_sentence_only(tmp_path: Path) -> None:
    from core.focus import FocusSession
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll
    from core.speech_profile import empty_profile
    from steps.focus import make_focus_step
    from store.profiles import ProfileStore

    owner = np.zeros(192, dtype=np.float32)
    owner[0] = 1.0
    profiles = ProfileStore(tmp_path / "anti.db")
    doc = empty_profile("spk_anti", owner.tolist())
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner, snr_db=12.0)
    assert finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)

    seen: list[tuple[float, float]] = []

    def verify(owner_doc, probe, min_mean, min_best_clip):
        seen.append((float(min_mean), float(min_best_clip)))
        return True, 0.95, "mean"

    session = FocusSession()
    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id="spk_anti",
        require_owner_enroll=True,
        mask_other_voices=False,
        verify_min_mean=0.45,
        verify_min_best_clip=0.50,
        wake_min_speech_ms=500,
    )
    wake = _pcm(_voiced(0.8))
    sentence = _pcm(_voiced(1.2))
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(sentence)
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["antispoof"] = {"raise_verify": 0.08, "action": "soft"}
    turn.notes["meta"] = {
        "wake": True,
        "source": "laptop",
        "wake_pcm_separate": True,
        "wake_b64": __import__("base64").b64encode(wake).decode(),
        "vol": 0.2,
    }
    with (
        mock.patch("steps.focus.embed_pcm16_mono", return_value=owner),
        mock.patch("steps.focus.speech_ms_in_pcm", return_value=800),
        mock.patch("steps.focus.verify_owner_robust", side_effect=verify),
    ):
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error is None
    assert cfg.verify_min_mean == 0.45
    assert cfg.verify_min_best_clip == 0.50
    assert len(seen) == 2
    assert seen[0] == pytest.approx((0.41, 0.46))
    assert seen[1] == pytest.approx((0.53, 0.58))


@pytest.mark.skipif(not WEIGHTS.is_file(), reason="AASIST-L.pth not downloaded")
def test_checkpoint_scores_one_second_of_noise() -> None:
    rng = np.random.default_rng(1)
    noise = rng.standard_normal(RATE).astype(np.float32) * 0.08
    cfg = AntispoofConfig(weights=str(WEIGHTS))
    assert weights_path(cfg).is_file()
    note = score_raw_pcm16(_pcm(noise), RATE, cfg, None)
    assert note["backend"] == "aasist_l", note
    assert isinstance(note["spoof_score"], float)
    assert 0.0 <= note["spoof_score"] <= 1.0
    assert note["action"] != "hard"
    assert note["spoof_score"] < AntispoofConfig().hard
    assert note["n_windows"] >= 1
    json.dumps(note, allow_nan=False)


def test_hard_stops_pipeline_before_later_step() -> None:
    ran: list[str] = []

    def later(turn: Turn) -> None:
        ran.append("later")

    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(_voiced(2.0)))
    turn.notes["channels"] = 1
    step = make_antispoof_step(_cfg(), lambda: None)
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        Pipeline([step, later], step_timeout_s=5).run(turn)
    assert turn.error == "spoof_suspected"
    assert ran == []
    json.dumps(turn.notes["antispoof"], allow_nan=False)


def test_soft_does_not_set_error_or_skip_later_step() -> None:
    ran: list[str] = []

    def later(turn: Turn) -> None:
        ran.append("later")

    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(_voiced(2.0)))
    turn.notes["channels"] = 1
    step = make_antispoof_step(_cfg(), lambda: None)
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(0.85)):
        Pipeline([step, later], step_timeout_s=5).run(turn)
    assert turn.error is None
    assert turn.notes["antispoof"]["action"] == "soft"
    assert ran == ["later"]


def test_thresholds_come_from_config() -> None:
    pcm = _pcm(_voiced(2.0))
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(0.90)):
        soft = score_raw_pcm16(pcm, RATE, _cfg(), None)
        allowed = score_raw_pcm16(pcm, RATE, _cfg(soft=0.95, hard=0.99), None)
        hard = score_raw_pcm16(pcm, RATE, _cfg(soft=0.50, hard=0.90), None)
    assert soft["action"] == "soft"
    assert soft["raise_verify"] == pytest.approx(0.08)
    assert allowed["action"] == "allow"
    assert allowed["raise_verify"] == 0
    assert hard["action"] == "hard"


def test_echo_cosine_is_not_a_vote() -> None:
    pcm = _pcm(_voiced(2.0))
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        note = score_raw_pcm16(
            pcm, RATE, _cfg(echo_corr=1.01, echo_cosine=0.0), pcm
        )
    assert note["echo_corr"] is not None and note["echo_corr"] > 0.9
    assert note["action"] == "hard"


def test_subsecond_and_silence_and_stub_model_cannot_hard_reject() -> None:
    short = _pcm(_voiced(0.5))
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0, reliable=True)):
        note = score_raw_pcm16(short, RATE, _cfg(), None)
    assert note["reliable"] is False
    assert note["action"] == "soft"
    assert note["spoof_score"] == pytest.approx(1.0)

    def explode(_path: object) -> None:
        raise AssertionError("silence must not load the model")

    quiet = _pcm(np.zeros(RATE * 2, dtype=np.float32))
    with mock.patch("core.antispoof.get_model", side_effect=explode):
        silent = score_raw_pcm16(quiet, RATE, _cfg(weights=str(WEIGHTS)), None)
    assert silent["action"] == "allow"
    assert silent["spoof_score"] is None

    with mock.patch("core.antispoof.get_model", return_value=None):
        stubbed = score_raw_pcm16(_pcm(_voiced(2.0)), RATE, _cfg(weights=str(WEIGHTS)), None)
    assert stubbed["backend"] == "aasist_l_unavailable"
    assert stubbed["spoof_score"] is None
    assert stubbed["action"] == "allow"


def test_nonfinite_score_fail_open() -> None:
    def infer(_samples, _weights, _backend):
        return {
            "backend": "aasist_l",
            "spoof_score": float("inf"),
            "spoof_score_max": float("nan"),
            "n_windows": 1,
            "reliable": True,
        }

    with mock.patch("core.antispoof.infer_aasist", infer):
        note = score_raw_pcm16(_pcm(_voiced(2.0)), RATE, _cfg(), None)
    assert note["action"] == "allow"
    assert note["spoof_score"] is None
    assert note["backend"] == "aasist_l_error: nonfinite"
    json.dumps(note, allow_nan=False)


def test_forward_exception_fail_open() -> None:
    def boom(_model, _windows):
        raise RuntimeError("forward blew up")

    with (
        mock.patch("core.antispoof.get_model", return_value=object()),
        mock.patch("core.antispoof._forward_spoof", side_effect=boom),
    ):
        note = score_raw_pcm16(_pcm(_voiced(2.0)), RATE, _cfg(), None)
    assert note["action"] == "allow"
    assert note["spoof_score"] is None
    assert note["backend"] == "aasist_l_error: RuntimeError"
    json.dumps(note, allow_nan=False)


def test_step_exception_fail_open_and_pipeline_continues() -> None:
    ran: list[str] = []

    def later(_turn: Turn) -> None:
        ran.append("later")

    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(_voiced(2.0)))
    turn.notes["channels"] = "nope"
    step = make_antispoof_step(_cfg(), lambda: None)
    Pipeline([step, later], step_timeout_s=5).run(turn)
    assert turn.error is None
    assert turn.notes["antispoof"]["action"] == "allow"
    assert turn.notes["antispoof"]["backend"] == "aasist_l_error: ValueError"
    assert bytes(turn.pcm_in)
    assert ran == ["later"]


def test_client_cannot_force_score_or_action() -> None:
    from core.client_meta import sanitize_client_meta

    meta = sanitize_client_meta(
        {
            "source": "laptop",
            "spoof_score": 0.0,
            "action": "allow",
            "raise_verify": 0,
            "antispoof": {"action": "allow", "spoof_score": 0.0},
        }
    )
    assert meta == {"source": "laptop"}
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(_voiced(2.0)))
    turn.notes["channels"] = 1
    turn.notes["meta"] = meta
    turn.notes["antispoof"] = {"action": "allow", "spoof_score": 0.0, "raise_verify": 0}
    step = make_antispoof_step(_cfg(), lambda: None)
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        step(turn)
    assert turn.error == "spoof_suspected"
    assert turn.notes["antispoof"]["action"] == "hard"
    assert turn.notes["antispoof"]["spoof_score"] == pytest.approx(1.0)


def test_stale_or_empty_playback_does_not_count_as_echo() -> None:
    import time

    from bridge import Session

    pcm = _pcm(_voiced(2.0))
    now = 10_000.0
    assert playback_for_echo(None, now, now) is None
    assert playback_for_echo(b"", now, now) is None
    assert playback_for_echo(pcm, None, now) is None
    assert playback_for_echo(pcm, now - 30.0, now) == pcm
    assert playback_for_echo(pcm, now - 30.01, now) is None

    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(pcm)
    turn.notes["channels"] = 1
    stale = make_antispoof_step(
        _cfg(), lambda: playback_for_echo(pcm, now - 31.0, now)
    )
    fresh = make_antispoof_step(
        _cfg(), lambda: playback_for_echo(pcm, now - 5.0, now)
    )
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        stale(turn)
    assert turn.notes["antispoof"]["action"] == "hard"
    assert turn.error == "spoof_suspected"

    turn2 = Turn(rate_hz=RATE)
    turn2.pcm_in = bytearray(pcm)
    turn2.notes["channels"] = 1
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        fresh(turn2)
    assert turn2.notes["antispoof"]["action"] == "soft"
    assert turn2.error is None

    class Stale:
        _last_pcm_out = pcm
        _last_pcm_out_at = 0.0

    class Fresh:
        _last_pcm_out = pcm
        _last_pcm_out_at = time.monotonic()

    class Empty:
        _last_pcm_out = b""
        _last_pcm_out_at = time.monotonic()

    assert Session._get_last_playback(Stale()) is None
    assert Session._get_last_playback(Fresh()) == pcm
    assert Session._get_last_playback(Empty()) is None


def test_long_clip_forward_batch_is_three_windows() -> None:
    import torch

    shapes: list[tuple[int, ...]] = []

    def fake_model(wave: torch.Tensor):
        shapes.append(tuple(int(n) for n in wave.shape))
        logits = torch.zeros(wave.shape[0], 2)
        logits[:, 0] = 20.0
        logits[:, 1] = -20.0
        return torch.zeros(wave.shape[0], 4), logits

    pcm = _pcm(_voiced(20.0))
    with mock.patch("core.antispoof.get_model", return_value=fake_model):
        note = score_raw_pcm16(pcm, RATE, _cfg(weights=str(WEIGHTS)), None)
    assert shapes == [(3, 64600)]
    assert note["n_windows"] == 3
    assert note["spoof_score"] > 0.9
    assert note["action"] == "hard"


def test_half_window_spacing_keeps_both_starts() -> None:
    # End start is exactly 32300 samples from 0, so both are kept.
    both = make_windows(np.zeros(64600 + 32300, dtype=np.float32))
    assert len(both) == 2
    assert all(w.shape == (64600,) for w in both)
    three = make_windows(np.zeros(64600 * 4, dtype=np.float32))
    assert len(three) == 3


def test_sha_mismatch_fail_open(tmp_path: Path) -> None:
    bad = tmp_path / "AASIST-L.pth"
    bad.write_bytes(b"not-the-pinned-checkpoint")
    pcm = _pcm(_voiced(2.0))
    note = score_raw_pcm16(pcm, RATE, AntispoofConfig(weights=str(bad)), pcm)
    assert note["backend"] == "aasist_l_unavailable"
    assert note["spoof_score"] is None
    assert note["action"] == "allow"
    assert note["echo_corr"] is not None and note["echo_corr"] > 0.9
    json.dumps(note, allow_nan=False)


def test_contract_rejects_antispoof_after_denoise_without_playback() -> None:
    with pytest.raises(ValueError, match="must run after"):
        validate_step_contract(["denoise", "antispoof"])


def test_load_config_rejects_antispoof_after_denoise(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "steps": ["denoise", "antispoof", "echo"],
                "antispoof": {"enabled": True},
                "denoise": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must run after"):
        load_config(bad)
    ok = tmp_path / "ok.json"
    ok.write_text(
        json.dumps(
            {
                "steps": ["antispoof", "denoise", "echo"],
                "antispoof": {"enabled": True, "weights": "models/no-such.pth"},
                "denoise": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config(ok)
    assert cfg.steps.index("antispoof") < cfg.steps.index("denoise")


def test_hello_status_ready_follows_the_file(tmp_path: Path) -> None:
    missing = hello_status(_cfg())
    assert missing["enabled"] is True
    assert missing["backend"] == "aasist_l"
    assert missing["ready"] is False
    present = tmp_path / "AASIST-L.pth"
    present.write_bytes(b"x")
    found = hello_status(AntispoofConfig(weights=str(present), enabled=False))
    assert found["ready"] is True
    assert found["enabled"] is False


def test_calibrate_reads_float_wav_the_stdlib_rejects(tmp_path: Path) -> None:
    import struct
    import subprocess

    from tools.calibrate_antispoof import load_mono_pcm16

    tone = load_mono_pcm16(ROOT / "tools" / "test-tone.wav")
    assert len(tone) == 32000
    stereo = load_mono_pcm16(ROOT / "tools" / "doa-test.wav")
    assert len(stereo) == 32000
    n = 160
    samples = struct.pack("<" + "f" * n, *([0.25] * n))
    fmt = struct.pack("<HHIIHH", 3, 1, 16000, 16000 * 4, 4, 32)
    body = (
        b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", len(samples))
        + samples
    )
    wav = tmp_path / "float.wav"
    wav.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)
    pcm = load_mono_pcm16(wav)
    vals = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    assert vals.shape == (n,)
    assert float(vals.mean()) == pytest.approx(0.25, abs=0.02)
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "calibrate_antispoof.py"),
            str(wav),
            "--weights",
            "models/no-such-AASIST-L.pth",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "action=allow" in proc.stdout
    assert "spoof_score=None" in proc.stdout


def test_failed_turn_notes_still_json_save(tmp_path: Path) -> None:
    from core.speech_profile import sanitize_notes_for_storage
    from store.db import TurnStore

    turn = Turn(rate_hz=RATE)
    turn.error = "spoof_suspected"
    turn.pcm_in = bytearray(_pcm(_voiced(1.2)))
    turn.notes["antispoof"] = {
        "action": "hard",
        "spoof_score": 0.99,
        "raise_verify": 0.0,
        "backend": "aasist_l",
        "leak": b"\x00\x01",
    }
    turn.notes["pcm_pre_denoise"] = b"\x00\x01\x02"
    turn.notes["numpy_score"] = np.float32(0.5)
    clean = sanitize_notes_for_storage(turn.notes)
    json.dumps(clean, allow_nan=False)
    assert "pcm_pre_denoise" not in clean
    assert "leak" not in clean["antispoof"]
    assert clean["numpy_score"] == pytest.approx(0.5)
    assert isinstance(clean["numpy_score"], float)
    store = TurnStore(tmp_path / "turns.db")
    store._save(turn)
    with store._connect() as conn:
        row = conn.execute("SELECT notes_json, error FROM turns").fetchone()
    saved = json.loads(row[0])
    assert row[1] == "spoof_suspected"
    assert saved["antispoof"]["action"] == "hard"
    assert "pcm_pre_denoise" not in saved


def test_focus_hard_action_is_not_wake_verified(tmp_path: Path) -> None:
    from core.focus import FocusSession
    from steps.focus import make_focus_step
    from store.profiles import ProfileStore

    session = FocusSession()
    cfg = FocusConfig(enabled=True, lock_owner=True, require_owner_enroll=True)
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(_pcm(_voiced(1.2)))
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["antispoof"] = {"action": "hard", "raise_verify": 0.08}
    turn.notes["focus_wake"] = {"verified": True, "match": 0.99}
    turn.notes["meta"] = {"wake": True, "source": "laptop"}
    with mock.patch("steps.focus.verify_owner_robust") as verify:
        make_focus_step(
            cfg, session, ProfileStore(tmp_path / "f.db"), DenoiseConfig(enabled=False)
        )(turn)
    assert turn.error == "spoof_suspected"
    verify.assert_not_called()


def test_stereo_survives_antispoof_into_the_next_step() -> None:
    mono = _pcm(_voiced(1.2))
    samples = np.frombuffer(mono, dtype="<i2")
    stereo = np.empty(samples.size * 2, dtype="<i2")
    stereo[0::2] = samples
    stereo[1::2] = samples
    raw = stereo.tobytes()
    seen: dict[str, object] = {}

    def later(turn: Turn) -> None:
        seen["pcm"] = bytes(turn.pcm_in)
        seen["channels"] = turn.notes.get("channels")

    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(raw)
    turn.notes["channels"] = 2
    step = make_antispoof_step(_cfg(), lambda: None)
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(0.2)):
        Pipeline([step, later], step_timeout_s=5).run(turn)
    assert seen["pcm"] == raw
    assert seen["channels"] == 2
    assert turn.error is None


def test_default_hard_is_saturated() -> None:
    """Pinned AASIST-L scored LJ Speech as high as 0.999993. Do not lower hard."""
    assert AntispoofConfig().hard == 1.0
    assert AntispoofConfig().hard >= 0.95


def test_one_second_delayed_echo_is_not_hard() -> None:
    voiced = _voiced(2.0)
    delay = 1600
    mic = np.concatenate(
        [np.zeros(delay, dtype=np.float32), voiced[: RATE - delay]]
    )
    assert mic.shape[0] == RATE
    corr = self_echo_corr(mic, voiced, RATE)
    assert corr is not None and corr > 0.9
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        note = score_raw_pcm16(_pcm(mic), RATE, _cfg(), _pcm(voiced))
    assert note["echo_corr"] is not None and note["echo_corr"] > 0.9
    assert note["action"] == "soft"
    assert note["spoof_score"] == pytest.approx(1.0)


def test_short_independent_noise_does_not_false_echo() -> None:
    rng = np.random.default_rng(2)
    mic = rng.standard_normal(RATE).astype(np.float32) * 0.2
    play = rng.standard_normal(RATE * 2).astype(np.float32) * 0.2
    corr = self_echo_corr(mic, play, RATE)
    assert corr is not None and corr < 0.55


def test_unsent_pcm_out_is_not_echo() -> None:
    pcm = _pcm(_voiced(2.0))
    turn = Turn(rate_hz=RATE)
    turn.pcm_in = bytearray(pcm)
    turn.pcm_out = bytearray(pcm)
    turn.notes["channels"] = 1
    step = make_antispoof_step(_cfg(), lambda: None)
    with mock.patch("core.antispoof.infer_aasist", _fake_infer(1.0)):
        step(turn)
    assert turn.notes["antispoof"]["echo_corr"] is None
    assert turn.notes["antispoof"]["action"] == "hard"
    assert turn.error == "spoof_suspected"


def test_contract_rejects_second_antispoof_after_denoise() -> None:
    with pytest.raises(ValueError, match="must run after"):
        validate_step_contract(["antispoof", "denoise", "antispoof"])


def test_load_config_rejects_second_antispoof_after_denoise(tmp_path: Path) -> None:
    bad = tmp_path / "dup.json"
    bad.write_text(
        json.dumps(
            {
                "steps": ["antispoof", "denoise", "antispoof", "echo"],
                "antispoof": {"enabled": True},
                "denoise": {"enabled": True},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must run after"):
        load_config(bad)


def test_laptop_spoof_message_names_synthetic_audio() -> None:
    from core.antispoof import SPOOF_SUSPECTED_MESSAGE

    src = (ROOT / "tools" / "laptop_voice.py").read_text(encoding="utf-8")
    assert "SPOOF_SUSPECTED_MESSAGE" in src
    assert "spoof_suspected" not in SPOOF_SUSPECTED_MESSAGE
    lowered = SPOOF_SUSPECTED_MESSAGE.lower()
    assert "synthetic" in lowered
    assert "replay" not in lowered
    assert "played-back" not in lowered
    assert "speaker" not in lowered
