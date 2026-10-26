from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from pathlib import Path

import websockets

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.antispoof import hello_status, playback_for_echo  # noqa: E402
from core.mood import client_view as mood_client_view  # noqa: E402
from core.mood import hello_status as mood_hello_status  # noqa: E402
from core.client_meta import sanitize_client_meta  # noqa: E402
from core.config import load_config  # noqa: E402
from core.env import load_dotenv  # noqa: E402
from core.doa import estimate_azimuth_deg, split_stereo_interleaved  # noqa: E402
from core.focus import FocusSession, sync_focus_from_owner  # noqa: E402
from core.listen_gate import pause_hold_ms  # noqa: E402
from core.meter import Meter  # noqa: E402
from core.netutil import format_port_busy_help, port_is_listening  # noqa: E402
from core.pipeline import Pipeline  # noqa: E402
from core.segment import SegmentStats, trim_pcm16  # noqa: E402
from core.turn import Turn  # noqa: E402
from core.vad_bridge import pcm16_to_mono  # noqa: E402
from core.utterance import apply_trim_and_vad, reject_reason  # noqa: E402
from steps.antispoof import make_antispoof_step  # noqa: E402
from steps.cadence import make_cadence_step  # noqa: E402
from steps.denoise import make_denoise_step  # noqa: E402
from steps.echo import echo_step  # noqa: E402
from steps.focus import make_focus_step  # noqa: E402
from steps.intent import make_intent_step  # noqa: E402
from steps.llm import make_llm_step  # noqa: E402
from steps.mood import make_mood_step  # noqa: E402
from steps.pronunciation import make_pronunciation_step  # noqa: E402
from steps.safety import make_safety_in_step, make_safety_out_step  # noqa: E402
from steps.stt import make_stt_step  # noqa: E402
from steps.tts import make_tts_step, weights_ready  # noqa: E402
from steps.context_retrieve import make_context_retrieve_step  # noqa: E402
from steps.memory_persist import make_memory_persist_step  # noqa: E402
from steps.research import make_research_step  # noqa: E402
from providers.memory_service import build_memory_service  # noqa: E402
from core.smart_turn import available as smart_turn_available  # noqa: E402
from core.wake import WakeDetector  # noqa: E402
from core.health_http import serve_health  # noqa: E402
from core.done_contract import stitch_done_message  # noqa: E402
from core.robot_actions import ALLOWED, plan_actions, with_ids  # noqa: E402
from store.action_log import ActionLog  # noqa: E402
from store.db import TurnStore  # noqa: E402
from store.profiles import ProfileStore  # noqa: E402
from store.retention import purge_old_turns  # noqa: E402
from steps.vision import image_bytes_ok, make_vision_step  # noqa: E402

CHUNK_BYTES = 640  # 20 ms @ 16 kHz mono PCM16
_ALLOWED_RATES = frozenset({16000})


def client_error(turn: Turn) -> dict:
    """Error JSON for a finished turn. A missing voice still carries the reply."""
    err: dict = {"type": "error", "reason": turn.error}
    if turn.notes.get("focus"):
        err["focus"] = turn.notes["focus"]
    if turn.notes.get("antispoof"):
        err["antispoof"] = turn.notes["antispoof"]
    mood_err = mood_client_view(turn.notes.get("mood"))
    if mood_err is not None:
        err["mood"] = mood_err
    if turn.error == "tts_unavailable":
        err["reply"] = turn.text_out or ""
        tts_note = turn.notes.get("tts")
        if isinstance(tts_note, dict):
            err["tts"] = tts_note
    return err


_connection_lock: asyncio.Lock | None = None
_active_connections = 0


def _resolve_channels(turn: Turn) -> int:
    ch = int(turn.notes.get("channels", 1))
    if ch != 1:
        return ch
    meta = turn.notes.get("meta") or {}
    if int(meta.get("channels", 1)) == 2:
        return 2
    if turn.notes.get("chunk_stereo_hint"):
        return 2
    return 1


def _trim_pcm(pcm: bytes, rate: int, channels: int) -> tuple[bytes, SegmentStats]:
    if channels <= 1:
        return trim_pcm16(pcm, rate)
    mono = pcm16_to_mono(pcm, 2)
    trimmed_mono, seg = trim_pcm16(mono, rate)
    if not trimmed_mono:
        return b"", seg
    lead_samples = seg.leading_trim_ms * rate // 1000
    trim_samples = int(seg.trim_s * rate)
    start = lead_samples * 4
    end = (lead_samples + trim_samples) * 4
    return pcm[start:end], seg


def build_pipeline(
    cfg,
    focus_session: FocusSession,
    profiles: ProfileStore,
    get_last_playback=None,
    meter: Meter | None = None,
    store: TurnStore | None = None,
    db_path: Path | None = None,
) -> Pipeline:
    if get_last_playback is None:
        get_last_playback = lambda: None
    mem_path = db_path or (ROOT / "astra.db")
    memory = build_memory_service(cfg.memory, mem_path)
    registry = {
        "echo": echo_step,
        "antispoof": make_antispoof_step(cfg.antispoof, get_last_playback),
        "denoise": make_denoise_step(cfg.denoise),
        "focus": make_focus_step(cfg.focus, focus_session, profiles, cfg.denoise),
        "stt": make_stt_step(cfg.stt),
        "safety_in": make_safety_in_step(cfg.safety, cfg.limits),
        "mood": make_mood_step(cfg.mood, profiles, cfg.focus, cfg.profile),
        "cadence": make_cadence_step(cfg.cadence, cfg.profile, profiles, cfg.focus),
        "pronunciation": make_pronunciation_step(
            cfg.pronunciation, cfg.profile, profiles, cfg.focus
        ),
        "context_retrieve": make_context_retrieve_step(
            cfg.memory, profiles, memory, mem_path
        ),
        "research": make_research_step(cfg.research),
        "llm": make_llm_step(cfg.llm, cfg.limits, meter, store, profiles),
        "intent": make_intent_step(cfg.limits),
        "safety_out": make_safety_out_step(cfg.safety, cfg.limits),
        "memory_persist": make_memory_persist_step(cfg.memory, memory),
        "tts": make_tts_step(cfg.tts),
        "vision": make_vision_step(cfg.vision),
    }
    steps = []
    for name in cfg.steps:
        fn = registry.get(name)
        if fn is None:
            raise ValueError(f"Unknown step: {name}")
        steps.append(fn)
    return Pipeline(steps, step_timeout_s=cfg.pipeline_step_timeout_s)


class Session:
    def __init__(
        self,
        ws,
        cfg,
        store: TurnStore,
        profiles: ProfileStore,
        meter: Meter,
        action_log: ActionLog,
    ):
        self.ws = ws
        self.cfg = cfg
        self.store = store
        self.profiles = profiles
        self.meter = meter
        self.action_log = action_log
        self._pending_image: dict | None = None
        self.focus_session = FocusSession()
        self._last_pcm_out: bytes | None = None
        self._last_pcm_out_at: float | None = None
        self.pipeline = build_pipeline(
            cfg,
            self.focus_session,
            profiles,
            self._get_last_playback,
            meter=meter,
            store=store,
            db_path=store.db_path,
        )
        self.busy = False
        self.turn: Turn | None = None
        self.rate = 16000
        self._barge = asyncio.Event()
        self._streaming = False
        self._barge_until = 0.0
        self._wake = self._build_wake_detector()
        self._authenticated = not cfg.security.require_auth
        if cfg.focus.enabled:
            sync_focus_from_owner(
                self.focus_session,
                profiles,
                cfg.focus.owner_speaker_id,
            )

    def _get_last_playback(self) -> bytes | None:
        # Set only after bytes leave the socket. Stale audio is not echo.
        # Barge does not clear a clip that was actually sent: the room can
        # still contain it, and that echo must not become a hard reject.
        return playback_for_echo(self._last_pcm_out, self._last_pcm_out_at)

    def _build_wake_detector(self) -> WakeDetector:
        fc = self.cfg.focus
        models_dir = ROOT / "models"
        custom = models_dir / "hey_astra.onnx"
        path = custom if custom.is_file() else None
        name = fc.wake_model if path is None else "hey_astra"
        return WakeDetector(
            model_path=path,
            model_name=name.replace("models/", "").replace(".onnx", ""),
            phrase=fc.wake_phrase,
            threshold=fc.wake_threshold,
        )

    def _wake_ready(self) -> bool:
        return self._wake.wake_ready()

    def _owner_enroll_complete(self) -> bool:
        from core.owner import find_owner_doc
        from core.owner_enroll import owner_enroll_complete

        doc = find_owner_doc(
            self.profiles.list_all(), self.cfg.focus.owner_speaker_id
        )
        return owner_enroll_complete(doc)

    async def send_json(self, obj: dict) -> None:
        await self.ws.send(json.dumps(obj))

    async def handle_hello(self, msg: dict) -> None:
        if self.cfg.security.require_auth:
            token = str(msg.get("token") or msg.get("auth") or "")
            expected = self.cfg.security.auth_token
            if not secrets.compare_digest(token, expected):
                await self.send_json({"type": "error", "reason": "auth"})
                self._authenticated = False
                return
            self._authenticated = True
        await self.send_json(
            {
                "type": "hello",
                "proto": self.cfg.proto,
                "limits": {
                    "max_clip_s": self.cfg.limits.max_clip_s,
                    "max_reply_s": self.cfg.limits.max_reply_s,
                    "min_clip_s": self.cfg.limits.min_clip_s,
                    "min_speech_s": self.cfg.limits.min_speech_s,
                    "end_silence_ms": self.cfg.limits.end_silence_ms,
                    "merge_gap_ms": self.cfg.limits.merge_gap_ms,
                    "pause_hold_ms": pause_hold_ms(
                        self.cfg.limits.end_silence_ms,
                        self.cfg.limits.merge_gap_ms,
                    ),
                    "min_speech_ratio": self.cfg.limits.min_speech_ratio,
                },
                "listen": {
                    "smart_turn_weights": self.cfg.listen.smart_turn_weights,
                    "smart_turn_ready": smart_turn_available(
                        self.cfg.listen.smart_turn_weights
                    ),
                    "fallback_end_silence_ms": self.cfg.listen.fallback_end_silence_ms,
                    "complete_close_ms": self.cfg.listen.complete_close_ms,
                    "max_extra_pause_ms": self.cfg.listen.max_extra_pause_ms,
                },
                "denoise": {
                    "enabled": self.cfg.denoise.enabled,
                    "backend": self.cfg.denoise.backend,
                },
                "antispoof": hello_status(self.cfg.antispoof),
                "focus": {
                    "enabled": self.cfg.focus.enabled,
                    "wake_phrase": self.cfg.focus.wake_phrase,
                    "wake_model": self.cfg.focus.wake_model,
                    "wake_threshold": self.cfg.focus.wake_threshold,
                    "wake_ready": self._wake_ready(),
                    "session_timeout_s": self.cfg.focus.session_timeout_s,
                    "min_enroll_s": self.cfg.focus.min_enroll_s,
                    "owner_enroll_complete": self._owner_enroll_complete(),
                    "require_owner_enroll": self.cfg.focus.require_owner_enroll,
                    "lock_owner": self.cfg.focus.lock_owner,
                },
                "vad": {
                    "site": self.cfg.vad.site,
                    "backend": self.cfg.vad.backend,
                    "frame_ms": self.cfg.vad.frame_ms,
                    "threshold": self.cfg.vad.threshold,
                    "min_speech_ms": self.cfg.vad.min_speech_ms,
                },
                "stt": {
                    "enabled": self.cfg.stt.enabled,
                    "model": self.cfg.stt.model,
                    "language": self.cfg.stt.language,
                    "auto_language": self.cfg.stt.auto_language,
                },
                "mood": mood_hello_status(self.cfg.mood),
                "cadence": {"enabled": self.cfg.cadence.enabled},
                "pronunciation": {"enabled": self.cfg.pronunciation.enabled},
                "llm": {
                    "enabled": self.cfg.llm.enabled,
                    # groq, then OpenRouter; or openrouter alone. Other names
                    # do not select a model.
                    "provider": self.cfg.llm.provider,
                },
                "tts": {
                    "enabled": self.cfg.tts.enabled,
                    "backend": self.cfg.tts.backend,
                    "ready": weights_ready(self.cfg.tts),
                },
                "vision": {"enabled": self.cfg.vision.enabled},
                "robot": {
                    "enabled": self.cfg.robot.enabled,
                    "actions": sorted(ALLOWED),
                },
            }
        )

    async def handle_image(self, msg: dict) -> None:
        if self.cfg.security.require_auth and not self._authenticated:
            await self.send_json({"type": "error", "reason": "auth"})
            return
        if not self.cfg.vision.enabled:
            await self.send_json({"type": "error", "reason": "vision_off"})
            return
        import base64

        raw_b64 = msg.get("image_b64") or msg.get("image") or ""
        if not isinstance(raw_b64, str) or not raw_b64.strip():
            await self.send_json({"type": "error", "reason": "bad image"})
            return
        if len(raw_b64) > self.cfg.vision.max_bytes * 2:
            await self.send_json({"type": "error", "reason": "image too large"})
            return
        try:
            data = base64.b64decode(raw_b64, validate=True)
        except Exception:
            await self.send_json({"type": "error", "reason": "bad image"})
            return
        if len(data) > self.cfg.vision.max_bytes:
            await self.send_json({"type": "error", "reason": "image too large"})
            return
        mime = str(msg.get("mime") or "image/jpeg").strip().lower()
        if mime not in ("image/jpeg", "image/jpg", "image/png"):
            await self.send_json({"type": "error", "reason": "bad mime"})
            return
        if not image_bytes_ok(data, mime):
            await self.send_json({"type": "error", "reason": "bad image"})
            return
        self._pending_image = {"bytes": data, "mime": mime}
        await self.send_json({"type": "image_ack", "bytes": len(data)})

    async def handle_barge(self) -> None:
        """Stop playback while chunks are in flight or the speaker is still playing them."""
        if self._streaming or time.monotonic() < self._barge_until:
            self._barge.set()
            if not self._streaming:
                await self.send_json({"type": "stop"})
                print("focus: barge — playback stopped")

    def _abort_start(self, *, reserved: float = 0.0) -> None:
        actual = self.turn.cost_usd if self.turn is not None else 0.0
        self.meter.settle(reserved, actual)
        self.turn = None
        self.busy = False

    async def handle_start(self, msg: dict) -> None:
        if self.busy:
            await self.send_json({"type": "busy"})
            return
        if self.cfg.security.require_auth and not self._authenticated:
            await self.send_json({"type": "error", "reason": "auth"})
            return
        if self.meter.over_cap():
            await self.send_json({"type": "error", "reason": "daily cap"})
            return
        cost_est = 0.0
        if not self.meter.try_reserve(cost_est):
            await self.send_json({"type": "error", "reason": "daily cap"})
            return
        self.busy = True
        rate = int(msg.get("rate", 16000))
        if rate not in _ALLOWED_RATES:
            await self.send_json({"type": "error", "reason": "bad rate"})
            self._abort_start(reserved=cost_est)
            return
        self.rate = rate
        self.turn = Turn(rate_hz=self.rate)
        self.turn.notes["cost_reserved"] = cost_est
        channels = int(msg.get("channels", 1))
        if channels not in (1, 2):
            await self.send_json({"type": "error", "reason": "bad channels"})
            self._abort_start(reserved=cost_est)
            return
        channels_explicit = "channels" in msg
        if "meta" in msg:
            clean = sanitize_client_meta(msg["meta"])
            self.turn.notes["meta"] = clean
            if clean.get("wake"):
                self.turn.notes["wake_turn"] = True
            meta_ch = clean.get("channels")
            if meta_ch is not None:
                try:
                    channels = int(meta_ch)
                except (TypeError, ValueError):
                    channels = 1
                if channels not in (1, 2):
                    channels = 1
                channels_explicit = True
        self.turn.notes["channels"] = channels
        self.turn.notes["channels_explicit"] = channels_explicit
        if self._pending_image is not None:
            self.turn.notes["vision_image"] = self._pending_image
            self._pending_image = None
        await self.send_json({"type": "started"})

    async def handle_audio(self, data: bytes) -> None:
        if not self.turn:
            return
        if not self.turn.notes.get("channels_explicit"):
            mono_chunk = self.rate * 20 // 1000 * 2
            stereo_chunk = mono_chunk * 2
            if len(data) == stereo_chunk and len(data) % mono_chunk == 0:
                self.turn.notes["chunk_stereo_hint"] = True
            elif len(data) == mono_chunk:
                self.turn.notes["chunk_stereo_hint"] = False

        channels = _resolve_channels(self.turn)
        max_bytes = self.cfg.limits.max_clip_s * self.rate * 2 * channels
        if len(self.turn.pcm_in) + len(data) > max_bytes:
            self.turn.error = "too long"
            return
        self.turn.pcm_in.extend(data)

    async def _stream_pcm_out(self, turn: Turn, pcm_out: bytes) -> bool:
        """Send reply PCM; return True if barged."""
        self._barge.clear()
        self._streaming = True
        barged = False
        sent = 0

        async def watcher() -> None:
            try:
                while True:
                    raw = await self.ws.recv()
                    if isinstance(raw, str):
                        obj = json.loads(raw)
                        if obj.get("type") == "barge":
                            self._barge.set()
                            return
            except asyncio.CancelledError:
                return
            except websockets.ConnectionClosed:
                self._barge.set()
                return

        task = asyncio.create_task(watcher())
        try:
            vol = turn.notes.get("volume")
            if vol:
                await self.send_json(
                    {
                        "type": "volume",
                        "gain": vol.get("gain", 1.0),
                        "firmware_vol": vol.get("firmware_vol"),
                        "distance_rel": vol.get("distance_rel"),
                    }
                )
            for i in range(0, len(pcm_out), CHUNK_BYTES):
                if self._barge.is_set():
                    barged = True
                    break
                chunk = pcm_out[i : i + CHUNK_BYTES]
                await self.ws.send(chunk)
                sent += len(chunk)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._streaming = False
            if sent:
                self._last_pcm_out = bytes(pcm_out[:sent])
                self._last_pcm_out_at = time.monotonic()

        if barged:
            await self.send_json({"type": "stop"})
            turn.notes["barged"] = True
            print("focus: barge — playback stopped")
            self._barge_until = 0.0
        else:
            play_s = len(pcm_out) / 2 / max(turn.rate_hz, 1)
            self._barge_until = time.monotonic() + play_s + 0.5
        return barged

    async def handle_end(self) -> None:
        turn_ref = self.turn
        try:
            await self._handle_end()
        except Exception as exc:
            import traceback

            print(f"turn failed: {exc}")
            traceback.print_exc()
            try:
                await self.send_json({"type": "error", "reason": "internal"})
            except Exception:
                pass
        finally:
            self.busy = False
            self.turn = None
            if turn_ref is not None:
                # After the pipeline, so the llm step's reserve is what settle refunds.
                raw_reserved = turn_ref.notes.get("cost_reserved", 0) or 0
                try:
                    reserved = float(raw_reserved)
                except (TypeError, ValueError):
                    reserved = 0.0
                self.meter.settle(reserved, turn_ref.cost_usd)

    async def _handle_end(self) -> None:
        if not self.turn:
            self.busy = False
            return
        turn = self.turn
        self.turn = None
        if turn.error == "too long":
            await self.send_json({"type": "error", "reason": "too long"})
            self.busy = False
            return
        if not turn.pcm_in:
            await self.send_json({"type": "error", "reason": "empty"})
            self.busy = False
            return

        meta = turn.notes.get("meta") or {}
        if self.cfg.focus.enabled:
            if self.focus_session.tick_timeout(self.cfg.focus.session_timeout_s):
                print("focus: session timeout — asleep")
                sync_focus_from_owner(
                    self.focus_session,
                    self.profiles,
                    self.cfg.focus.owner_speaker_id,
                )
            elif not self.focus_session.state.armed:
                sync_focus_from_owner(
                    self.focus_session,
                    self.profiles,
                    self.cfg.focus.owner_speaker_id,
                )
            wake_turn = bool(meta.get("wake") or turn.notes.get("wake_turn"))
            if not self.focus_session.state.armed and not wake_turn:
                reason = "asleep"
                if (
                    self.cfg.focus.require_owner_enroll
                    and not self._owner_enroll_complete()
                ):
                    reason = "need_enroll"
                await self.send_json({"type": "error", "reason": reason})
                self.busy = False
                return

        raw_len = len(turn.pcm_in)
        raw_pcm = bytes(turn.pcm_in)
        channels = _resolve_channels(turn)
        turn.notes["channels"] = channels
        if channels == 2 and not turn.notes.get("channels_explicit"):
            m = turn.notes.get("meta") or {}
            if int(m.get("channels", 1)) != 2:
                turn.notes["channels_inferred"] = True

        trimmed, seg = _trim_pcm(raw_pcm, turn.rate_hz, channels)
        turn.notes["raw_audio_bytes"] = raw_len
        turn.notes["trim_audio_bytes"] = len(trimmed)

        lim = self.cfg.limits
        if not trimmed:
            await self.send_json({"type": "error", "reason": "empty"})
            self.busy = False
            return

        apply_trim_and_vad(turn, trimmed, seg)
        reason = reject_reason(seg, turn, lim)
        if reason:
            print(
                f"utterance rejected: {reason} "
                f"(trim={seg.trim_s:.2f}s vad_ms={turn.notes.get('speech_ms', 0)})"
            )
            await self.send_json({"type": "error", "reason": reason})
            self.busy = False
            return

        lab_synthetic = meta.get("source") == "doa_sim"
        if channels == 2 and trimmed:
            left, right = split_stereo_interleaved(trimmed)
            angle, conf = estimate_azimuth_deg(
                left, right, turn.rate_hz, baseline_m=self.cfg.doa.baseline_m
            )
            turn.notes["doa_confidence"] = round(conf, 4)
            turn.notes["doa_raw_deg"] = round(angle, 2)
            if conf >= self.cfg.doa.min_confidence:
                turn.notes["azimuth_deg"] = round(
                    angle + self.cfg.doa.offset_deg, 2
                )
            az_out = turn.notes.get("azimuth_deg")
            if lab_synthetic:
                if az_out is not None:
                    print(f"doa (lab/sim): azimuth_deg={az_out} confidence={conf:.3f}")
            elif az_out is not None:
                print(
                    f"doa: azimuth_deg={az_out} confidence={conf:.3f} "
                    f"(raw={angle:.1f})"
                )
            elif not lab_synthetic:
                print(f"doa: low confidence {conf:.3f} — no aim sent")

        if not self.cfg.stt.enabled:
            turn.text_in = f"[audio {seg.trim_s:.1f}s]"
        print(
            f"utterance ok: speech {seg.trim_s:.2f}s "
            f"(from {seg.raw_s:.2f}s raw, vad {turn.notes.get('speech_ms', 0)} ms)"
        )
        await asyncio.to_thread(self.pipeline.run, turn)
        lim = self.cfg.limits
        if turn.text_in and len(turn.text_in) > lim.max_text_chars:
            turn.text_in = turn.text_in[: lim.max_text_chars]
            turn.notes["text_truncated"] = True
        if turn.text_out and len(turn.text_out) > lim.max_reply_chars:
            turn.text_out = turn.text_out[: lim.max_reply_chars]
            turn.notes["reply_text_truncated"] = True
        if turn.notes.get("antispoof"):
            a = turn.notes["antispoof"]
            print(
                f"antispoof: {a.get('action')} score={a.get('spoof_score')} "
                f"echo={a.get('echo_corr')} backend={a.get('backend')}"
            )
        if turn.notes.get("denoise"):
            d = turn.notes["denoise"]
            print(
                f"denoise: {d.get('backend')} "
                f"snr {d.get('snr_before_db')} -> {d.get('snr_after_db')} dB"
            )
        if turn.notes.get("focus_replaced"):
            print("focus: now following new voice")
        if turn.notes.get("focus"):
            f = turn.notes["focus"]
            print(
                f"focus: gate={f.get('gate', 'ok')} match={f.get('match')} "
                f"wake={f.get('wake_match', '')} mixed_ms={f.get('mixed_ms', 0)}"
            )
        if turn.notes.get("volume"):
            v = turn.notes["volume"]
            print(
                f"volume: gain={v.get('gain')} "
                f"(you sound {'quieter' if v.get('gain', 1) > 1 else 'louder'} than wake)"
            )
        if turn.notes.get("transcript") is not None:
            print(f"transcript: {turn.notes.get('transcript') or '(empty)'}")
        mood_view = mood_client_view(turn.notes.get("mood"))
        if mood_view is not None:
            label = mood_view.get("label") or "null"
            try:
                conf_s = f"{float(mood_view.get('confidence')):.2f}"
            except (TypeError, ValueError):
                conf_s = "0"
            print(f"mood: label={label} conf={conf_s} backend={mood_view.get('backend')}")
        if turn.notes.get("cadence"):
            c = turn.notes["cadence"]
            print(
                f"cadence: peaks={c.get('peaks_per_s')}/s "
                f"median_pause={c.get('pause_ms_median')}ms"
            )
        if turn.notes.get("llm"):
            llm = turn.notes["llm"]
            llm_bits = [f"llm: ok={llm.get('ok')}"]
            if llm.get("provider"):
                llm_bits.append(f"provider={llm.get('provider')}")
            if llm.get("reason"):
                llm_bits.append(f"reason={llm.get('reason')}")
            if llm.get("skipped"):
                llm_bits.append(f"skipped={llm.get('skipped')}")
            if llm.get("detail"):
                llm_bits.append(f"detail={llm.get('detail')}")
            print(" ".join(llm_bits))
        if turn.notes.get("speaker_id"):
            print(f"profile: speaker_id={turn.notes['speaker_id']}")
        if turn.error:
            await self.send_json(client_error(turn))
            self.store.save_async(turn)
            self.busy = False
            return

        max_reply_bytes = lim.max_reply_s * turn.rate_hz * 2
        if len(turn.pcm_out) > max_reply_bytes:
            turn.pcm_out = turn.pcm_out[:max_reply_bytes]
            turn.notes["reply_truncated"] = True

        await self._stream_pcm_out(turn, bytes(turn.pcm_out))

        claimed: list[dict] = []
        if self.cfg.robot.enabled:
            planned = with_ids(
                turn,
                plan_actions(turn, require_owner=self.cfg.robot.require_owner),
            )
            claimed = [
                action
                for action in planned
                if self.action_log.claim(
                    str(action["id"]),
                    turn_id=turn.id,
                    action_name=str(action["name"]),
                )
            ]
        aim = None
        if "azimuth_deg" in turn.notes:
            aim = {
                "azimuth_deg": turn.notes["azimuth_deg"],
                "confidence": turn.notes.get("doa_confidence", 0),
            }
        body: dict = {
            "utterance": {
                "raw_s": round(seg.raw_s, 3),
                "speech_s": round(seg.trim_s, 3),
                "speech_ms": turn.notes.get("speech_ms", 0),
                "onset_ms": turn.notes.get("onset_ms", 0),
                "vad_backend": turn.notes.get("vad_backend", "rms"),
            }
        }
        if turn.notes.get("noise_after"):
            body["utterance"]["noise"] = turn.notes["noise_after"]
        if turn.notes.get("denoise"):
            body["utterance"]["denoise"] = turn.notes["denoise"]
        if turn.notes.get("antispoof"):
            body["antispoof"] = turn.notes["antispoof"]
        if turn.notes.get("focus"):
            body["focus"] = turn.notes["focus"]
        if turn.notes.get("focus_warn"):
            body["focus_warn"] = turn.notes["focus_warn"]
        if turn.notes.get("volume"):
            body["volume"] = turn.notes["volume"]
        if mood_view is not None:
            body["mood"] = mood_view
        if turn.notes.get("cadence"):
            body["cadence"] = turn.notes["cadence"]
        if turn.notes.get("pronunciation"):
            body["pronunciation"] = turn.notes["pronunciation"]
        if turn.notes.get("vision"):
            body["vision"] = turn.notes["vision"]
        if "transcript" in turn.notes:
            body["transcript"] = turn.notes["transcript"]
        if turn.notes.get("language"):
            body["language"] = turn.notes["language"]
        if turn.notes.get("language_probability") is not None:
            body["language_probability"] = turn.notes["language_probability"]
        if turn.notes.get("speaker_id"):
            body["speaker_id"] = turn.notes["speaker_id"]
        if turn.notes.get("barged"):
            body["barged"] = True
        body["reply"] = turn.text_out or ""
        done_msg = stitch_done_message(
            turn.id,
            actions=claimed or None,
            aim=aim,
            body=body,
        )
        await self.send_json(done_msg)
        if turn.notes.get("pronunciation_learn_pending"):
            asyncio.create_task(self._pronunciation_learn_async(turn))
        self.store.save_async(turn)
        self.busy = False

    async def _pronunciation_learn_async(self, turn: Turn) -> None:
        sid = turn.notes.get("speaker_id")
        if not sid:
            return
        doc = self.profiles.get(sid)
        if not doc:
            return
        cfg = self.cfg.pronunciation

        def _work():
            from core.pronunciation_learn import run_pronunciation_learn

            return run_pronunciation_learn(turn, doc, cfg)

        try:
            summary = await asyncio.wait_for(
                asyncio.to_thread(_work), timeout=cfg.aligner_timeout_s
            )
            from core.pronunciation_learn import merge_pronunciation_into

            fresh = self.profiles.get(sid) or doc
            merge_pronunciation_into(fresh, doc)
            self.profiles.put(fresh)
            if summary.get("lines") or summary.get("skipped_words"):
                await self.send_json({"type": "learn", **summary})
        except asyncio.TimeoutError:
            print("pronunciation learn: timeout (skipped)")
        except Exception as exc:
            print(f"pronunciation learn failed: {exc}")


async def handler(
    ws, cfg, store: TurnStore, profiles: ProfileStore, meter: Meter, action_log: ActionLog
):
    global _active_connections
    peer = getattr(ws, "remote_address", None)
    lock = _connection_lock
    assert lock is not None
    async with lock:
        if _active_connections >= cfg.security.max_connections:
            await ws.close(1013, "too many connections")
            return
        _active_connections += 1
    print(f"client connected {peer}")
    session = Session(ws, cfg, store, profiles, meter, action_log)
    try:
        async for message in ws:
            if isinstance(message, str):
                try:
                    msg = json.loads(message)
                except json.JSONDecodeError:
                    await session.send_json({"type": "error", "reason": "bad json"})
                    continue
                t = msg.get("type")
                if t == "hello":
                    await session.handle_hello(msg)
                elif t == "start":
                    await session.handle_start(msg)
                elif t == "end":
                    await session.handle_end()
                elif t == "barge":
                    await session.handle_barge()
                elif t == "image":
                    await session.handle_image(msg)
            else:
                if session._streaming:
                    continue
                await session.handle_audio(message)
    except websockets.ConnectionClosed:
        print(f"client disconnected {peer}")
    finally:
        async with lock:
            _active_connections -= 1


async def main_async(host: str, port: int, config_path: Path | None = None) -> None:
    global _connection_lock
    _connection_lock = asyncio.Lock()
    cfg = load_config(config_path)
    cfg.host = host
    cfg.port = port

    if port_is_listening(port):
        print(format_port_busy_help(port), file=sys.stderr)
        raise SystemExit(1)

    db_path = Path(os.environ.get("ASTRA_DB", str(ROOT / "astra.db")))
    store = TurnStore(db_path)
    profiles = ProfileStore(db_path)
    meter = Meter(db_path, cfg.daily_cost_cap_usd)
    action_log = ActionLog(db_path)
    if cfg.store_audio_days > 0:
        removed = purge_old_turns(db_path, keep_days=cfg.store_audio_days)
        if removed:
            print(f"retention: purged {removed} old turn rows")

    if cfg.stt.enabled:
        from steps.stt import warmup_stt

        print(
            f"stt: loading Whisper {cfg.stt.model} "
            f"(first run may download; please wait)…",
            flush=True,
        )
        await asyncio.to_thread(warmup_stt, cfg.stt)
        print(f"stt: ready ({cfg.stt.model})", flush=True)

    if cfg.tts.enabled:
        from steps.tts import warmup_tts, weights_ready

        if weights_ready(cfg.tts):
            await asyncio.to_thread(warmup_tts, cfg.tts)
            print("tts: ready (piper)", flush=True)

    health_server = None
    if cfg.health.enabled:
        payload: dict = {
            "ok": True,
            "service": "astra-bridge",
            "proto": cfg.proto,
        }
        if host in ("127.0.0.1", "localhost", "::1"):
            payload["ws_port"] = port
        health_port = cfg.health.port if cfg.health.port else port + 1
        try:
            health_server = await serve_health(host, health_port, payload)
        except OSError as exc:
            if exc.errno in (98, 10048) and health_port != 0:
                health_server = await serve_health(host, 0, payload)
            else:
                print(f"health: disabled ({exc})", file=sys.stderr)
        if health_server is not None and health_server.sockets:
            bound = int(health_server.sockets[0].getsockname()[1])
            print(f"health: http://127.0.0.1:{bound}/health")

    try:
        async with websockets.serve(
            lambda ws: handler(ws, cfg, store, profiles, meter, action_log),
            host,
            port,
            max_size=2**20,
            ping_interval=20,
            ping_timeout=300,
        ):
            for w in cfg.step_warnings:
                print(f"config: {w}")
            flags = [
                "antispoof=ON" if cfg.antispoof.enabled else "antispoof=OFF",
                "mood=ON" if cfg.mood.enabled else "mood=OFF",
                "llm=ON" if cfg.llm.enabled else "llm=OFF",
                "tts=ON" if cfg.tts.enabled else "tts=OFF",
            ]
            if cfg.denoise.enabled:
                flags.append("denoise=ON")
            if cfg.focus.enabled:
                flags.append("focus=ON")
            if cfg.stt.enabled:
                flags.append("stt=ON")
            if cfg.cadence.enabled:
                flags.append("cadence=ON")
            if cfg.pronunciation.enabled:
                flags.append("pronounce=ON")
            extra = f" {' '.join(flags)}" if flags else ""
            print(
                f"bridge ready on ws://127.0.0.1:{port} "
                f"(LAN: ws://<your-laptop-ip>:{port}) steps={cfg.steps}{extra}"
            )
            if cfg.host == "127.0.0.1":
                print(
                    "Listening on localhost only. "
                    "For robot/Wi-Fi set host in config or run: "
                    "set ASTRA_BIND_ALL=1"
                )
            if cfg.security.require_auth:
                print("Auth: clients must send token in hello (ASTRA_AUTH_TOKEN).")
            elif cfg.vision.enabled and host not in ("127.0.0.1", "localhost", "::1"):
                print(
                    "Warning: vision is on without auth on a non-local bind — "
                    "set ASTRA_AUTH_TOKEN before exposing this bridge.",
                    flush=True,
                )
            print("Press Ctrl+C to stop.")
            await asyncio.Future()
    except OSError as exc:
        if exc.errno in (98, 10048):  # EADDRINUSE / WSAEADDRINUSE
            print(format_port_busy_help(port), file=sys.stderr)
            raise SystemExit(1) from exc
        raise


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Astra voice bridge (echo / AI pipeline)")
    p.add_argument("--host", default=None, help="bind address (default from config)")
    p.add_argument("--port", type=int, default=None, help="TCP port (default 8765)")
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to config.json (default server/config.json or config.example.json)",
    )
    return p.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    cfg = load_config(args.config)
    host = args.host if args.host is not None else cfg.host
    port = args.port if args.port is not None else cfg.port
    try:
        asyncio.run(main_async(host, port, args.config))
    except KeyboardInterrupt:
        print("\nbridge stopped.")


if __name__ == "__main__":
    main()
