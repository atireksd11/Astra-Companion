from __future__ import annotations

import base64
import math
import struct
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import DenoiseConfig, FocusConfig  # noqa: E402
from core.distance_volume import compute_playback_gain  # noqa: E402
from core.focus import FocusSession, sync_focus_from_owner  # noqa: E402
from core.owner import find_owner_doc  # noqa: E402
from core.speech_profile import empty_profile  # noqa: E402
from core.turn import Turn  # noqa: E402
from steps.focus import make_focus_step  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402

SR = 16000


def _tone(hz: float, seconds: float, amp: float = 0.4) -> bytes:
    n = int(SR * seconds)
    out = []
    for i in range(n):
        s = int(amp * 32767 * math.sin(2 * math.pi * hz * i / SR))
        out.append(struct.pack("<h", s))
    return b"".join(out)


def _fake_ecapa(pcm: bytes, rate: int = 16000) -> np.ndarray:
    if not pcm:
        return np.zeros(192, dtype=np.float32)
    s = np.frombuffer(pcm, dtype=np.int16).astype(np.float64)
    bucket = int(abs(s[: min(len(s), 800)].mean()) % 192)
    v = np.zeros(192, dtype=np.float32)
    v[bucket] = 1.0
    v[(bucket + 17) % 192] = 0.3
    hz_hint = int(len(pcm) // 100) % 192
    v[hz_hint] += 0.2
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-8 else v


@contextmanager
def _patch_ecapa(side_effect=_fake_ecapa):
    with (
        mock.patch("core.speaker_ecapa.embed_pcm16_mono", side_effect=side_effect),
        mock.patch("core.focus.embed_pcm16_mono", side_effect=side_effect),
        mock.patch("steps.focus.embed_pcm16_mono", side_effect=side_effect),
    ):
        yield


def _step(session: FocusSession, profiles: ProfileStore, cfg: FocusConfig | None = None):
    return make_focus_step(
        cfg
        or FocusConfig(
            enabled=True,
            min_similarity=0.40,
            lock_owner=False,
            mask_other_voices=False,
            require_owner_enroll=False,
        ),
        session,
        profiles,
        DenoiseConfig(enabled=False),
    )


def test_gain_clamped() -> None:
    g = compute_playback_gain(5000, 1000, min_gain=0.45, max_gain=1.8)
    assert g["gain"] == 1.8
    g2 = compute_playback_gain(1000, 5000, min_gain=0.45, max_gain=1.8)
    assert g2["gain"] == 0.45


def test_focus_keeps_full_clip_of_enrolled_voice(tmp_path: Path) -> None:
    pcm = _tone(200, 1.5)
    session = FocusSession()
    profiles = ProfileStore(tmp_path / "t.db")
    with _patch_ecapa():
        session.on_wake(
            _tone(200, 3.2),
            rate=SR,
            azimuth_deg=None,
            speech_ms=3200,
            min_enroll_ms=3000,
        )
        turn = Turn(rate_hz=SR)
        turn.pcm_in = bytearray(pcm)
        turn.notes["channels"] = 1
        turn.notes["meta"] = {"vol": 0.2}
        _step(session, profiles)(turn)
    assert turn.error is None
    assert bytes(turn.pcm_in) == pcm


def test_focus_publishes_owner_mask_as_analysis_audio(tmp_path: Path, monkeypatch) -> None:
    pcm = _tone(200, 1.5)
    masked = b"\x01\x00" * (len(pcm) // 2)

    def fake_mask(*_args, **_kwargs):
        return masked, 120, 0.4

    monkeypatch.setattr("steps.focus.mask_pcm_to_owner", fake_mask)
    session = FocusSession()
    profiles = ProfileStore(tmp_path / "mask.db")
    cfg = FocusConfig(
        enabled=True,
        min_similarity=0.40,
        lock_owner=False,
        mask_other_voices=True,
        require_owner_enroll=False,
        echo_use_owner_mask=False,
    )
    with _patch_ecapa():
        session.on_wake(
            _tone(200, 3.2),
            rate=SR,
            azimuth_deg=None,
            speech_ms=3200,
            min_enroll_ms=3000,
        )
        turn = Turn(rate_hz=SR)
        turn.pcm_in = bytearray(pcm)
        turn.notes["channels"] = 1
        turn.notes["meta"] = {"vol": 0.2}
        _step(session, profiles, cfg)(turn)
    assert turn.error is None
    assert bytes(turn.pcm_in) == pcm
    assert turn.pcm_mood == masked
    assert turn.pcm_for_analysis == pcm
    vec_a = np.zeros(192, dtype=np.float32)
    vec_a[0] = 1.0
    vec_b = np.zeros(192, dtype=np.float32)
    vec_b[1] = 1.0

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        return vec_a if len(pcm) > 60000 else vec_b

    session = FocusSession()
    profiles = ProfileStore(tmp_path / "t.db")
    with _patch_ecapa(side_effect=side):
        session.on_wake(
            _tone(150, 3.2),
            rate=SR,
            azimuth_deg=None,
            speech_ms=3200,
            min_enroll_ms=3000,
        )
        turn = Turn(rate_hz=SR)
        turn.pcm_in = bytearray(_tone(950, 1.0))
        turn.notes["channels"] = 1
        turn.notes["meta"] = {}
        _step(session, profiles)(turn)
    assert turn.error == "not your voice"


def test_ecapa_profile_without_is_owner_is_not_owner() -> None:
    ghost = empty_profile("spk_ghost", [0.1] * 192)
    ghost["match"]["method"] = "ecapa192"
    assert find_owner_doc([ghost]) is None


def test_sync_focus_from_owner_arms_session(tmp_path: Path) -> None:
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    profiles = ProfileStore(tmp_path / "t.db")
    doc = empty_profile("spk_o", [])
    doc["is_owner"] = True
    v = np.zeros(192, dtype=np.float32)
    v[0] = 1.0
    for _ in range(4):
        append_enroll_clip(doc, v, snr_db=10.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)
    session = FocusSession()
    assert sync_focus_from_owner(session, profiles)
    assert session.state.armed
    assert session.state.enrolled is not None
    assert session.state.enrolled.size == 192


def test_asleep_without_wake(tmp_path: Path) -> None:
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(_tone(200, 1.0))
    turn.notes["channels"] = 1
    turn.notes["meta"] = {}
    _step(FocusSession(), ProfileStore(tmp_path / "t.db"))(turn)
    assert turn.error == "asleep"


def test_lock_owner_blocks_wake_replace_legacy_profile(tmp_path: Path) -> None:
    profiles = ProfileStore(tmp_path / "t.db")
    legacy = {
        "speaker_id": "spk_owner",
        "is_owner": True,
        "match": {"embedding": [0.1] * 13, "method": "mfcc"},
        "pronunciation": {"lexicon": []},
        "updated_at": 1.0,
    }
    profiles.put(legacy)
    session = FocusSession()
    turn = Turn(rate_hz=SR)
    wake = _tone(200, 0.6)
    turn.pcm_in = bytearray(wake + _tone(200, 1.0))
    turn.notes["channels"] = 1
    turn.notes["meta"] = {
        "wake": True,
        "wake_b64": __import__("base64").b64encode(wake).decode(),
        "wake_speech_ms": 600,
    }
    cfg = FocusConfig(
        enabled=True,
        min_similarity=0.40,
        lock_owner=True,
        require_owner_enroll=False,
    )
    with _patch_ecapa():
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error == "not your voice"
    doc = profiles.get("spk_owner")
    assert len(doc["match"]["embedding"]) == 13


def test_legacy_13d_enroll_rejected(tmp_path: Path) -> None:
    session = FocusSession()
    session.state.armed = True
    session.state.enrolled = np.ones(13, dtype=np.float32)
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(_tone(200, 1.0))
    turn.notes["channels"] = 1
    turn.notes["meta"] = {}
    with _patch_ecapa():
        _step(session, ProfileStore(tmp_path / "t.db"))(turn)
    assert turn.error == "not your voice"


def test_laptop_wake_separate_keeps_full_sentence_for_verify(tmp_path: Path) -> None:
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    owner_vec = _fake_ecapa(_tone(200, 1.0))
    profiles = ProfileStore(tmp_path / "t.db")
    sid = "spk_o1"
    doc = empty_profile(sid, [])
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner_vec, snr_db=12.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)

    wake = _tone(200, 2.6)
    sentence = _tone(220, 6.0)
    body_embed_len: list[int] = []

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        if len(pcm) >= len(sentence) * 0.9:
            body_embed_len.append(len(pcm))
        return owner_vec

    session = FocusSession()
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(sentence)
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["meta"] = {
        "wake": True,
        "source": "laptop",
        "wake_pcm_separate": True,
        "wake_b64": base64.b64encode(wake).decode(),
        "wake_speech_ms": 600,
    }
    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        require_owner_enroll=True,
        mask_other_voices=False,
    )
    with (
        _patch_ecapa(side),
        mock.patch(
            "steps.focus.verify_owner_robust", return_value=(True, 0.9, "test")
        ),
    ):
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error is None
    assert body_embed_len == [len(sentence)]


def test_prepended_wake_strips_prefix_for_robot_style_pcm(tmp_path: Path) -> None:
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    owner_vec = _fake_ecapa(_tone(200, 1.0))
    profiles = ProfileStore(tmp_path / "t.db")
    sid = "spk_o2"
    doc = empty_profile(sid, [])
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner_vec, snr_db=12.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)

    wake = _tone(200, 2.6)
    sentence = _tone(220, 6.0)
    body_embed_len: list[int] = []

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        if len(pcm) >= len(sentence) * 0.5:
            body_embed_len.append(len(pcm))
        return owner_vec

    session = FocusSession()
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(wake + sentence)
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["meta"] = {
        "wake": True,
        "wake_b64": base64.b64encode(wake).decode(),
        "wake_speech_ms": 600,
    }
    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        require_owner_enroll=True,
        mask_other_voices=False,
    )
    with (
        _patch_ecapa(side),
        mock.patch(
            "steps.focus.verify_owner_robust", return_value=(True, 0.9, "test")
        ),
    ):
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error is None
    assert body_embed_len == [len(sentence)]


def test_verified_wake_accepts_owner_sentence_with_low_body_score(tmp_path: Path) -> None:
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    owner_vec = _fake_ecapa(_tone(200, 1.0))
    profiles = ProfileStore(tmp_path / "t.db")
    sid = "spk_o3"
    doc = empty_profile(sid, [])
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner_vec, snr_db=12.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)

    calls = {"n": 0}

    def verify(owner_doc, probe, min_mean, min_best_clip):
        calls["n"] += 1
        if calls["n"] == 1:
            return True, 0.71, "mean"
        return False, 0.07, "mean"

    wake = _tone(200, 0.8)
    sentence = _tone(220, 4.0)
    session = FocusSession()
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(sentence)
    turn.pcm_pre_denoise = sentence
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["meta"] = {
        "wake": True,
        "source": "laptop",
        "wake_pcm_separate": True,
        "wake_b64": base64.b64encode(wake).decode(),
    }
    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        require_owner_enroll=True,
        mask_other_voices=False,
        wake_min_speech_ms=500,
    )
    with (
        _patch_ecapa(),
        mock.patch("steps.focus.verify_owner_robust", side_effect=verify),
    ):
        make_focus_step(cfg, session, profiles, DenoiseConfig(enabled=False))(turn)
    assert turn.error is None
    assert calls["n"] == 2


def _enrolled_owner(tmp_path: Path, db_name: str):
    from core.owner_enroll import append_enroll_clip, finalize_owner_enroll

    owner_vec = _fake_ecapa(_tone(200, 1.0))
    profiles = ProfileStore(tmp_path / db_name)
    sid = "spk_fresh"
    doc = empty_profile(sid, [])
    doc["is_owner"] = True
    for _ in range(4):
        append_enroll_clip(doc, owner_vec, snr_db=12.0)
    finalize_owner_enroll(doc, min_clips=4)
    profiles.put(doc)
    return profiles, sid, owner_vec


def _wake_turn(wake: bytes, sentence: bytes) -> Turn:
    turn = Turn(rate_hz=SR)
    turn.pcm_in = bytearray(sentence)
    turn.pcm_pre_denoise = sentence
    turn.notes["channels"] = 1
    turn.notes["wake_turn"] = True
    turn.notes["meta"] = {
        "wake": True,
        "source": "laptop",
        "wake_pcm_separate": True,
        "wake_b64": base64.b64encode(wake).decode(),
    }
    return turn


def test_wake_clip_is_denoised_with_fresh_denoiser(tmp_path: Path) -> None:
    from core.denoise import DenoiseResult

    profiles, sid, owner_vec = _enrolled_owner(tmp_path, "fresh.db")
    wake = _tone(200, 0.8)
    sentence = _tone(220, 2.0)
    cleaned = b"\x11\x22" * (len(wake) // 2)
    seen: list[tuple] = []
    embedded: list[bytes] = []

    def fake_denoise(pcm, rate, *, backend, strength):
        seen.append((pcm, rate, backend, strength))
        return DenoiseResult(cleaned, "rnnoise", 1.0, 2.0)

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        embedded.append(bytes(pcm))
        return owner_vec

    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        require_owner_enroll=True,
        mask_other_voices=False,
        wake_min_speech_ms=500,
    )
    denoise = DenoiseConfig(enabled=True, backend="rnnoise", strength=0.7)
    with (
        _patch_ecapa(side),
        mock.patch("steps.focus.denoise_pcm16_fresh", side_effect=fake_denoise),
        mock.patch("steps.focus.verify_owner_robust", return_value=(True, 0.8, "mean")),
    ):
        make_focus_step(cfg, FocusSession(), profiles, denoise)(_wake_turn(wake, sentence))
    assert seen == [(wake, SR, "rnnoise", 0.7)]
    assert embedded[0] == cleaned
    assert embedded[0] != wake


def test_wake_clip_embeds_raw_when_fresh_denoise_fails(tmp_path: Path) -> None:
    from core.denoise import DenoiseResult

    profiles, sid, owner_vec = _enrolled_owner(tmp_path, "raw.db")
    wake = _tone(200, 0.8)
    sentence = _tone(220, 2.0)
    embedded: list[bytes] = []

    def side(pcm: bytes, rate: int = 16000) -> np.ndarray:
        embedded.append(bytes(pcm))
        return owner_vec

    cfg = FocusConfig(
        enabled=True,
        lock_owner=True,
        owner_speaker_id=sid,
        require_owner_enroll=True,
        mask_other_voices=False,
        wake_min_speech_ms=500,
    )
    denoise = DenoiseConfig(enabled=True, backend="rnnoise", strength=0.5)

    def run(effect) -> None:
        embedded.clear()
        with (
            _patch_ecapa(side),
            mock.patch("steps.focus.denoise_pcm16_fresh", side_effect=effect),
            mock.patch(
                "steps.focus.verify_owner_robust", return_value=(True, 0.8, "mean")
            ),
        ):
            make_focus_step(cfg, FocusSession(), profiles, denoise)(
                _wake_turn(wake, sentence)
            )

    run(lambda *a, **k: DenoiseResult(b"", "rnnoise", 0.0, 0.0))
    assert embedded[0] == wake
    run(RuntimeError("rnnoise"))
    assert embedded[0] == wake


def test_fresh_denoiser_does_not_use_shared_rnnoise(monkeypatch) -> None:
    import sys
    import types

    import core.denoise as denoise

    class _Local:
        def __init__(self, sample_rate: int = 16000) -> None:
            self.sample_rate = sample_rate

        def reset(self) -> None:
            return None

        def denoise_chunk(self, arr, partial: bool = True):
            yield np.array([1.0], dtype=np.float32), np.asarray(arr, dtype=np.int16)

    fake = types.ModuleType("pyrnnoise")
    fake.RNNoise = _Local
    monkeypatch.setitem(sys.modules, "pyrnnoise", fake)
    sentinel = object()
    monkeypatch.setattr(denoise, "_RNNOISE", sentinel)
    monkeypatch.setattr(denoise, "_RNNOISE_IMPORT_OK", None)

    def _shared():
        raise AssertionError("shared RNNoise")

    monkeypatch.setattr(denoise, "_get_rnnoise", _shared)
    pcm = b"\x01\x00" * 1600
    result = denoise.denoise_pcm16_fresh(pcm, SR, backend="rnnoise", strength=0.5)
    assert denoise._RNNOISE is sentinel
    assert result.backend == "rnnoise"
    assert result.pcm == pcm
