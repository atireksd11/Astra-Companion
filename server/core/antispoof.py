"""AASIST-L soft gate on raw 16 kHz PCM, plus a numpy self-echo check.

Score audio before denoise. Denoise wipes the vocoder cues this model uses.
The score is soft: higher spoof_score means more spoof-like, range [0, 1].
Class 0 is spoof, class 1 is bonafide.

Self-echo (the mic resembles the last playback) is a separate signal. It never
hard-rejects. Correlation is the v1 echo vote. Speaker-embedding cosine is not
computed here: embed_pcm16_mono loads ECAPA, and this step runs before focus
has an embedding. echo_cosine stays in config for a later pass.

Notes stored on the turn are plain JSON values. PCM stays on the Turn.
"""

from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

import numpy as np

from core.config import AntispoofConfig

WINDOW_SAMPLES = 64600
HALF_WINDOW = WINDOW_SAMPLES // 2  # 32300
MIN_RELIABLE_SAMPLES = 16000  # 1.0 s at 16 kHz
SILENCE_RMS = 0.005
ECHO_TEMPLATE_S = 1.0
ECHO_MAX_LAG_S = 0.400
ECHO_LAG_STEP = 16
# A 1.0 s mic cannot hold a 1.0 s template at a 400 ms lag. Score the overlap
# when at least this much still lines up, so a delayed copy is not a hard reject.
MIN_ECHO_OVERLAP_S = 0.50
PLAYBACK_MIN_RMS = 0.01
# Echo may hide a hard reject only while the speaker could still be ringing.
PLAYBACK_MAX_AGE_S = 30.0
EXPECTED_SHA256 = "814331d088032bb4c3fa61cc014789eadeed464209dd094ab3a2dd6ffbdce27a"
SERVER_ROOT = Path(__file__).resolve().parent.parent

# Shown by the laptop client. This gate is a waveform countermeasure, not a
# replay detector, so the text does not mention a speaker in the room.
SPOOF_SUSPECTED_MESSAGE = (
    "bridge: that clip's waveform looked synthetic, so it was dropped. "
    "Speak live into the mic."
)

_lock = threading.Lock()
_model = None
_model_key: str | None = None
_fail_key: str | None = None
_warned_keys: set[str] = set()


def weights_path(cfg: AntispoofConfig) -> Path:
    path = Path(cfg.weights)
    if not path.is_absolute():
        path = SERVER_ROOT / path
    return path


def weights_ready(cfg: AntispoofConfig) -> bool:
    """True when the weight file is on disk. Does not load the model."""
    return weights_path(cfg).is_file()


def hello_status(cfg: AntispoofConfig) -> dict:
    """Fields the hello message reports. ready is the file on disk, not a loaded model."""
    return {
        "enabled": bool(cfg.enabled),
        "backend": str(cfg.backend),
        "ready": bool(weights_ready(cfg)),
    }


def playback_for_echo(
    pcm: bytes | None,
    played_at: float | None,
    now: float | None = None,
    max_age_s: float = PLAYBACK_MAX_AGE_S,
) -> bytes | None:
    """Return playback only if it was sent inside the recent play window.

    Empty audio is not an echo template. A clip older than max_age_s must not
    keep downgrading hard scores after the speaker has gone quiet.
    """
    if not pcm or played_at is None:
        return None
    if now is None:
        now = time.monotonic()
    if float(now) - float(played_at) > float(max_age_s):
        return None
    return bytes(pcm)


def is_reliable(n_samples: int) -> bool:
    """Clips shorter than 1.0 s are tile-padded and must not hard-reject."""
    return int(n_samples) >= MIN_RELIABLE_SAMPLES


def make_windows(samples: np.ndarray) -> list[np.ndarray]:
    """Eval windows of exactly 64600 samples.

    Longer clips use up to three starts (start, middle, end). A later start is
    dropped when it is closer than half a window to one already kept. Exactly
    half a window apart (32300 samples) is kept. Shorter clips are tiled.
    """
    x = np.asarray(samples, dtype=np.float32).reshape(-1)
    n = int(x.shape[0])
    if n <= 0:
        return []
    if n < WINDOW_SAMPLES:
        reps = (WINDOW_SAMPLES + n - 1) // n
        tiled = np.tile(x, reps)[:WINDOW_SAMPLES]
        return [np.ascontiguousarray(tiled, dtype=np.float32)]
    if n == WINDOW_SAMPLES:
        return [np.ascontiguousarray(x, dtype=np.float32)]
    raw = [0, (n - WINDOW_SAMPLES) // 2, n - WINDOW_SAMPLES]
    kept: list[int] = []
    for start in raw:
        if any(abs(start - prev) < HALF_WINDOW for prev in kept):
            continue
        kept.append(int(start))
    return [
        np.ascontiguousarray(x[s : s + WINDOW_SAMPLES], dtype=np.float32) for s in kept
    ]


def _as_float(samples: np.ndarray) -> np.ndarray:
    x = np.asarray(samples).reshape(-1)
    if x.size == 0:
        return np.zeros(0, dtype=np.float32)
    if np.issubdtype(x.dtype, np.integer):
        return x.astype(np.float32) / 32768.0
    return x.astype(np.float32, copy=False)


def pcm16_to_float(pcm: bytes) -> np.ndarray:
    if not pcm or len(pcm) < 2:
        return np.zeros(0, dtype=np.float32)
    n = len(pcm) // 2
    return np.frombuffer(pcm[: n * 2], dtype="<i2").astype(np.float32) / 32768.0


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(x, dtype=np.float64))))


def _highest_rms_window(x: np.ndarray, win: int, hop: int = 160) -> np.ndarray:
    n = int(x.shape[0])
    if n <= win:
        return x[:win]
    energy = np.cumsum(np.square(x.astype(np.float64, copy=False)))
    best_i = 0
    best_e = -1.0
    last = n - win
    i = 0
    while True:
        prev = float(energy[i - 1]) if i else 0.0
        e = float(energy[i + win - 1]) - prev
        if e > best_e:
            best_e = e
            best_i = i
        if i == last:
            break
        i = min(last, i + hop)
    return x[best_i : best_i + win]


def self_echo_corr(
    mic: np.ndarray,
    playback: np.ndarray,
    rate: int = 16000,
) -> float | None:
    """Absolute Pearson correlation of the best lag from 0 to 400 ms.

    The template is the 1.0 s highest-RMS slice of playback. Lags step by 16
    samples. When the mic is too short to hold the whole template at that lag,
    the overlapping piece is scored if at least 0.5 s lines up. Returns None
    when either side is shorter than that 1.0 s template (which covers clips
    under 0.2 s), when the template RMS is below 0.01, or when no lag has a
    defined correlation. Correlation is the echo vote. Speaker cosine is not
    computed in v1.
    """
    if rate <= 0:
        return None
    mic_f = _as_float(mic)
    play_f = _as_float(playback)
    template_len = int(rate * ECHO_TEMPLATE_S)
    if mic_f.size < template_len or play_f.size < template_len:
        return None
    template = _highest_rms_window(play_f, template_len).astype(np.float64, copy=False)
    if _rms(template) < PLAYBACK_MIN_RMS:
        return None
    max_lag = int(round(ECHO_MAX_LAG_S * rate))
    min_overlap = max(2, int(round(rate * MIN_ECHO_OVERLAP_S)))
    mic64 = mic_f.astype(np.float64, copy=False)
    best: float | None = None
    for lag in range(0, max_lag + 1, ECHO_LAG_STEP):
        seg = mic64[lag:]
        overlap = min(template_len, int(seg.shape[0]))
        if overlap < min_overlap:
            break
        piece_t = template[:overlap]
        piece_s = seg[:overlap]
        piece_t = piece_t - float(piece_t.mean())
        piece_s = piece_s - float(piece_s.mean())
        t_energy = float(np.dot(piece_t, piece_t))
        s_energy = float(np.dot(piece_s, piece_s))
        if t_energy < 1e-12 or s_energy < 1e-12:
            continue
        corr = abs(float(np.dot(piece_t, piece_s) / np.sqrt(t_energy * s_energy)))
        if best is None or corr > best:
            best = corr
    return best


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _warn_once(key: str, message: str) -> None:
    if key in _warned_keys:
        return
    _warned_keys.add(key)
    print(message)


def _load_state(path: Path):
    """Load the pinned MIT checkpoint. weights_only=False only after sha256."""
    import torch

    sha_ok = _sha256(path) == EXPECTED_SHA256
    if not sha_ok:
        raise RuntimeError("AASIST-L.pth sha256 does not match the pinned checkpoint")
    try:
        state = torch.load(path, map_location="cpu", weights_only=True)
    except Exception:
        state = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(state, dict) and "pos_S" not in state:
        for key in ("state_dict", "model", "model_state_dict"):
            nested = state.get(key)
            if isinstance(nested, dict):
                state = nested
                break
    if not isinstance(state, dict):
        raise RuntimeError("AASIST-L checkpoint is not a state_dict")
    if any(str(k).startswith("module.") for k in state):
        state = {str(k).replace("module.", "", 1): v for k, v in state.items()}
    return state


def get_model(path: Path):
    """Lazy-load AASIST-L on CPU. None if the file is missing or will not load."""
    global _model, _model_key, _fail_key
    if not path.is_file():
        return None
    stat = path.stat()
    key = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    with _lock:
        if _model is not None and _model_key == key:
            return _model
        if _fail_key == key:
            return None
        try:
            # Reject a bad file before building the network or unpickling weights.
            if _sha256(path) != EXPECTED_SHA256:
                raise RuntimeError(
                    "AASIST-L.pth sha256 does not match the pinned checkpoint"
                )
            from core.aasist_l import build_aasist_l

            model = build_aasist_l()
            state = _load_state(path)
            model.load_state_dict(state)
            model.eval()
            for param in model.parameters():
                param.requires_grad_(False)
            _model = model
            _model_key = key
            _fail_key = None
            return model
        except Exception as exc:
            _fail_key = key
            # A bad path must not drop a model that already loaded for another file.
            if _model_key == key:
                _model = None
                _model_key = None
            _warn_once(
                key,
                f"antispoof: AASIST-L unavailable ({exc.__class__.__name__}: {exc}) "
                "— allowing audio",
            )
            return None


def _forward_spoof(model, windows: list[np.ndarray]) -> tuple[float, float]:
    import torch

    batch = np.stack(windows, axis=0)
    # The vendored sinc layer writes self.filters, and thread count is process-wide.
    with _lock:
        prev = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            with torch.no_grad():
                # (N, 64600). forward unsqueezes to (N, 1, T).
                wave = torch.from_numpy(batch)
                _hidden, logits = model(wave)
                probs = torch.softmax(logits, dim=-1)[:, 0]
                score = float(probs.mean().item())
                score_max = float(probs.max().item())
        finally:
            torch.set_num_threads(prev)
    return score, score_max


def infer_aasist(samples: np.ndarray, weights: Path, backend: str) -> dict:
    """Run AASIST-L. Fail-open dict when the backend cannot score."""
    n = int(np.asarray(samples).reshape(-1).shape[0])
    reliable = is_reliable(n)
    empty = {
        "backend": "aasist_l_unavailable",
        "spoof_score": None,
        "spoof_score_max": None,
        "n_windows": 0,
        "reliable": reliable,
    }
    if backend != "aasist_l":
        return empty
    windows = make_windows(samples)
    if not windows:
        return empty
    model = get_model(weights)
    if model is None:
        return empty
    try:
        score, score_max = _forward_spoof(model, windows)
    except Exception as exc:
        _warn_once(
            f"forward:{weights}",
            f"antispoof: AASIST-L forward failed ({exc.__class__.__name__}: {exc}) "
            "— allowing audio",
        )
        failed = dict(empty)
        failed["backend"] = f"aasist_l_error: {exc.__class__.__name__}"
        return failed
    return {
        "backend": "aasist_l",
        "spoof_score": score,
        "spoof_score_max": score_max,
        "n_windows": len(windows),
        "reliable": reliable,
    }


def decide_action(
    spoof_score: float | None,
    reliable: bool,
    echo_hit: bool,
    cfg: AntispoofConfig,
) -> tuple[str, float]:
    """Return (action, raise_verify). Echo never produces a hard reject."""
    if spoof_score is None:
        return "allow", 0.0
    if reliable and (not echo_hit) and float(spoof_score) >= float(cfg.hard):
        return "hard", 0.0
    if float(spoof_score) >= float(cfg.soft):
        return "soft", float(cfg.raise_verify)
    return "allow", 0.0


def _json_float(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out == float("inf") or out == float("-inf"):
        return None
    return out


def score_raw_pcm16(
    pcm: bytes,
    rate: int,
    cfg: AntispoofConfig,
    playback: bytes | None = None,
) -> dict:
    """Score raw mono PCM16. Always computes echo when playback is present."""
    mic = pcm16_to_float(pcm)
    play = pcm16_to_float(playback) if playback else np.zeros(0, dtype=np.float32)
    echo = self_echo_corr(mic, play, rate) if playback else None
    echo_hit = echo is not None and echo >= float(cfg.echo_corr)
    reliable = rate == 16000 and is_reliable(mic.shape[0])
    rms = _rms(mic)
    silent = mic.size == 0 or rms < SILENCE_RMS or rate != 16000

    if silent:
        backend = "aasist_l"
        if cfg.backend != "aasist_l" or not weights_path(cfg).is_file():
            backend = "aasist_l_unavailable"
        return {
            "backend": backend,
            "spoof_score": None,
            "spoof_score_max": None,
            "n_windows": 0,
            "reliable": bool(reliable),
            "echo_corr": _json_float(echo),
            "action": "allow",
            "raise_verify": 0.0,
        }

    inferred = infer_aasist(mic, weights_path(cfg), cfg.backend)
    # Hard-reject needs a finite score from a loaded model.
    raw_score = inferred["spoof_score"] if inferred["backend"] == "aasist_l" else None
    score = _json_float(raw_score)
    nonfinite = raw_score is not None and score is None
    model_loaded = score is not None
    if nonfinite:
        action, raise_verify = "allow", 0.0
        backend = "aasist_l_error: nonfinite"
    else:
        action, raise_verify = decide_action(
            score,
            bool(inferred["reliable"]) and model_loaded and reliable,
            echo_hit,
            cfg,
        )
        backend = "aasist_l" if model_loaded else str(inferred["backend"])
    return {
        "backend": backend,
        "spoof_score": score,
        "spoof_score_max": _json_float(inferred["spoof_score_max"]) if model_loaded else None,
        "n_windows": int(inferred["n_windows"]) if model_loaded else 0,
        "reliable": bool(reliable),
        "echo_corr": _json_float(echo),
        "action": action,
        "raise_verify": float(raise_verify),
    }
