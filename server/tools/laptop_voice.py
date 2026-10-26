"""
Talk into the laptop mic; hear the bridge reply on laptop speakers.

When hello says tts is enabled, playback is Piper. When tts.ready is false,
the reply is printed and the voice is unavailable.

Requires: bridge.py running on the same PC.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import sounddevice as sd
import websockets

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.antispoof import SPOOF_SUSPECTED_MESSAGE  # noqa: E402
from core.env import load_dotenv  # noqa: E402
from core.listen_gate import UtteranceGate, pause_hold_ms  # noqa: E402
from core.silero_client import (  # noqa: E402
    frame_is_speech_hysteresis,
    speech_ms_in_pcm,
)
from core.wake import WakeDetector  # noqa: E402

SAMPLE_RATE = 16000
SILERO_FRAME_SAMPLES = 512
WAKE_FRAME_SAMPLES = 2560  # 160 ms, one Zipformer chunk
WAKE_BUFFER_FRAMES = 16  # ~2.5 s at 160 ms
CHUNK_BYTES = 640
MAX_SEC = 15
END_SILENCE_MS = 2000
MERGE_GAP_MS = 2000
ECHO_GUARD_MS = 900
FOCUS_ARMED = False
FOCUS_ENABLED = False
FOCUS_LOCK_OWNER = False
WAKE_READY = False
VAD_THRESHOLD = 0.5
MIN_SPEECH_MS = 280
LAPTOP_BARGE = False
WAKE_LABEL = "Hey Astra"


def _wake_label_from_phrase(phrase: str) -> str:
    parts = (phrase or "hey astra").strip().split()
    if not parts:
        return "Hey Astra"
    return " ".join(p[:1].upper() + p[1:] if len(p) > 1 else p.upper() for p in parts)


def _stand_in_wake_note(wake: WakeDetector) -> str | None:
    """Custom hey_astra.onnx is optional. Spoken Hey Astra still works without it."""
    if wake.uses_kws():
        return None
    if wake.uses_phrase_spotter():
        return "Say Hey Astra to wake. Enter still works."
    return None
NOISY_ROOM = False
SMART_TURN_WEIGHTS = "models/smart-turn-v3.2-cpu.onnx"
FALLBACK_END_SILENCE_MS = 4500
COMPLETE_CLOSE_MS = 500


def _poll_enter_pressed() -> bool:
    """Non-blocking Enter (Windows); avoids a stuck background input() thread."""
    if sys.platform != "win32":
        return False
    import msvcrt

    hit = False
    while msvcrt.kbhit():
        if msvcrt.getwch() in ("\r", "\n"):
            hit = True
    return hit


def _read_bytes(stream: sd.RawInputStream, n_samples: int) -> bytes:
    data, _ = stream.read(n_samples)
    return bytes(data)


def record_one_utterance(
    *,
    vad_threshold: float = VAD_THRESHOLD,
    min_speech_ms: int = MIN_SPEECH_MS,
    arm_delay_ms: int = 0,
    noisy_room: bool = NOISY_ROOM,
) -> bytes:
    hold_ms = pause_hold_ms(END_SILENCE_MS, MERGE_GAP_MS)
    gate = UtteranceGate(
        frame_ms=32,
        min_speech_ms=min_speech_ms,
        end_silence_ms=hold_ms,
        max_ms=MAX_SEC * 1000,
        preroll_ms=300,
        silence_break_frames=6 if noisy_room else 4,
    )
    cont_th = 0.68 if noisy_room else max(vad_threshold + 0.1, 0.58)
    end_th = 0.35 if noisy_room else 0.38
    told_hold = False
    finish = threading.Event()
    if sys.platform != "win32":
        def _enter_finish() -> None:
            try:
                input()
                finish.set()
            except EOFError:
                finish.set()

        threading.Thread(target=_enter_finish, daemon=True).start()
    extra = (
        "Noisy-room mode: ignoring faint background speech; press Enter when done."
        if noisy_room
        else "Background chatter? Press Enter when you finish speaking."
    )
    print(
        f"Listening… (pause under {hold_ms / 1000:.1f}s mid-sentence is OK; "
        f"stay quiet {hold_ms / 1000:.1f}s when finished. {extra})"
    )

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=SILERO_FRAME_SAMPLES,
    ) as stream:
        guard_frames = max(0, arm_delay_ms // 32)
        for _ in range(guard_frames):
            _read_bytes(stream, SILERO_FRAME_SAMPLES)

        while not gate.closed:
            if finish.is_set() or _poll_enter_pressed():
                gate.finish_now()
                if gate.closed:
                    print("\n(Finished — Enter.)")
                break
            frame = _read_bytes(stream, SILERO_FRAME_SAMPLES)
            is_speech = frame_is_speech_hysteresis(
                frame,
                capturing=gate.capturing,
                start_threshold=vad_threshold,
                continue_threshold=cont_th,
                end_threshold=end_th,
            )
            was_capturing = gate.capturing
            status = gate.push(is_speech, frame)
            if not was_capturing and gate.capturing:
                print(
                    "\nHeard you — keep going or pause briefly, then stay quiet when finished."
                )
            if status == "hold" and not told_hold:
                print("Pause… still listening for the rest of your sentence.")
                told_hold = True
            if status == "pause_check":
                from core.smart_turn import predict_turn_complete

                done = predict_turn_complete(bytes(gate.pcm), weights=SMART_TURN_WEIGHTS)
                if done is False:
                    gate.defer_close()
                    if not told_hold:
                        print("Pause… still listening for the rest of your sentence.")
                        told_hold = True
                else:
                    gate.mark_turn_complete()

    pcm = bytes(gate.pcm)
    if len(pcm) < CHUNK_BYTES:
        return b""
    cap_s = len(pcm) / 2 / SAMPLE_RATE
    print(f"Captured {cap_s:.1f}s of audio", end="")
    if gate.hit_max:
        print(f" (hit {MAX_SEC}s limit)")
    else:
        print()
    return pcm


def _wait_for_wake(wake: WakeDetector) -> tuple[bool, bytes, int, bool]:
    """Returns (ok, wake_pcm, wake_speech_ms, enter_only)."""
    if wake.available() or wake.wake_ready():
        print(f'Asleep — say "{WAKE_LABEL}", then pause. Or press Enter…')
    else:
        print("Asleep — wake model unavailable; press Enter to wake…")

    enter = threading.Event()
    woke = {"hit": False}

    def _enter_wait() -> None:
        try:
            input()
            enter.set()
        except EOFError:
            enter.set()

    if sys.platform != "win32":
        threading.Thread(target=_enter_wait, daemon=True).start()
    buffer: deque[bytes] = deque(maxlen=WAKE_BUFFER_FRAMES)
    # openWakeWord keeps the last hit in its buffer. Without a reset the next
    # listen prints "Wake phrase heard" on silence and that clip scores ~0.07.
    wake.reset()
    # Ignore a leftover Jarvis score for 800 ms. A real "Hey Astra" phrase hit
    # still counts, and those frames stay in the clip for the voice check.
    flush_left = 5  # ~800 ms at 160 ms frames

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=WAKE_FRAME_SAMPLES,
        latency=0.2,
    ) as stream:
        while not enter.is_set():
            if _poll_enter_pressed():
                enter.set()
                break
            chunk = _read_bytes(stream, WAKE_FRAME_SAMPLES)
            buffer.append(chunk)
            hit = wake.feed_pcm16_mono(chunk, SAMPLE_RATE)
            if flush_left > 0:
                flush_left -= 1
                # Keyword and hey_astra.onnx hits count immediately. A frame
                # with no hit is only the startup flush.
                if not hit or wake._last_source not in ("phrase", "kws", "model"):
                    continue
            if hit:
                woke["hit"] = True
                print('Wake phrase heard (mic — not Enter).')
                for _ in range(6):
                    buffer.append(_read_bytes(stream, WAKE_FRAME_SAMPLES))
                enter.set()
                break

    if enter.is_set() and not woke["hit"]:
        wake.mark_wake()
        print("Wake (Enter).")
        return True, b"", 0, True

    # The 32-frame deque is ~2.5s of room audio. Prefer the keyword clip when
    # the spotter kept one. The ONNX path has no phrase clip.
    wake_pcm = b"".join(buffer)
    if woke["hit"]:
        getter = getattr(wake, "last_phrase_pcm", None)
        phrase: bytes | None = None
        if callable(getter):
            try:
                got = getter()
            except Exception:
                got = None
            if isinstance(got, (bytes, bytearray)):
                phrase = bytes(got)
        if phrase is not None and len(phrase) >= int(0.4 * SAMPLE_RATE) * 2:
            wake_pcm = phrase
    wake_ms = 0
    if wake_pcm:
        wake_ms = speech_ms_in_pcm(wake_pcm, VAD_THRESHOLD)
        wake_ms = max(wake_ms, speech_ms_in_pcm(wake_pcm, 0.35))
    if woke["hit"]:
        wake_ms = max(wake_ms, 550)
    return True, wake_pcm, wake_ms, False


def _print_learn(obj: dict) -> None:
    for line in obj.get("lines") or []:
        print(line)
    skipped = int(obj.get("skipped_words") or 0)
    if skipped:
        print(f"pronunciation: skipped {skipped} words (whisper confidence)")


def _tts_unavailable_message(obj: dict) -> str:
    reply = str(obj.get("reply") or "")
    shown = f"Astra: {reply}\n" if reply else ""
    return f"{shown}Astra can't speak aloud right now (tts_unavailable)."


def _hello_voice_warning(hello: dict) -> str | None:
    """Match hello tts.ready. A missing voice file is not an echo failure."""
    tts = hello.get("tts")
    if not isinstance(tts, dict) or not tts.get("enabled"):
        return None
    if tts.get("ready"):
        return None
    return "Astra can't speak aloud right now (tts_unavailable)."


def _no_audio_message(voice: bool, *, barged: bool) -> str:
    if barged:
        if voice:
            return "Voice was interrupted before audio arrived."
        return "Echo was interrupted before audio arrived."
    if voice:
        return "No voice audio returned — check the bridge window."
    return "No echo audio returned — check bridge window."


def _print_turn_summary(done: dict, *, voice: bool = False) -> None:
    if done.get("focus_warn") == "noisy_room_partial":
        print("(Noisy room: echo may be choppy — only your voice windows were kept.)")
    tx = done.get("transcript")
    if tx is not None:
        print(f"Transcript: {tx or '(empty)'}")
    lang = done.get("language")
    if isinstance(lang, str) and lang:
        prob = done.get("language_probability")
        if isinstance(prob, (int, float)):
            print(f"Language: {lang} ({float(prob):.2f})")
        else:
            print(f"Language: {lang}")
    reply = done.get("reply")
    if isinstance(reply, str) and reply:
        print(f"Astra: {reply}")
    utt = done.get("utterance") or {}
    raw_s = utt.get("raw_s")
    speech_s = utt.get("speech_s")
    if raw_s is not None and speech_s is not None:
        if voice:
            print(f"Speech: {speech_s:.2f}s (captured {raw_s:.2f}s)")
        else:
            print(f"Speech: echoed {speech_s:.2f}s (captured {raw_s:.2f}s)")
    mood = done.get("mood")
    if isinstance(mood, dict):
        label = mood.get("label")
        if label in ("happy", "sad", "angry", "neutral", "surprised"):
            try:
                conf = float(mood.get("confidence") or 0)
            except (TypeError, ValueError):
                conf = 0.0
            print(f"Mood: {label} ({conf:.2f})")
        else:
            print("Mood: uncertain")


async def send_utterance(
    ws,
    pcm: bytes,
    *,
    wake: bool = False,
    wake_pcm: bytes | None = None,
    wake_speech_ms: int = 0,
    enter_wake: bool = False,
) -> tuple[bytes, dict]:
    meta = {
        "noise": 100,
        "level": 500,
        "vol": 0.2,
        "source": "laptop",
        "wake_pcm_separate": True,
    }
    if wake:
        meta["wake"] = True
        if enter_wake:
            meta["enter_wake"] = True
        elif wake_pcm:
            meta["wake_phrase_ok"] = True
        if wake_pcm:
            meta["wake_b64"] = base64.b64encode(wake_pcm).decode("ascii")
            meta["wake_speech_ms"] = wake_speech_ms
    await ws.send(
        json.dumps(
            {
                "type": "start",
                "rate": SAMPLE_RATE,
                "meta": meta,
            }
        )
    )
    for i in range(0, len(pcm), CHUNK_BYTES):
        await ws.send(pcm[i : i + CHUNK_BYTES])
    await ws.send(json.dumps({"type": "end"}))

    out = bytearray()
    done: dict = {"type": "done"}
    barged = False
    while True:
        try:
            msg = await ws.recv()
        except websockets.exceptions.ConnectionClosedError as exc:
            raise RuntimeError(
                "Lost connection to bridge while waiting for a reply. "
                "Restart bridge.py and try again (first STT load can take a while)."
            ) from exc
        if isinstance(msg, str):
            obj = json.loads(msg)
            if obj.get("type") == "done":
                done = obj
                if barged:
                    done["barged"] = True
                break
            if obj.get("type") == "started":
                continue
            if obj.get("type") == "learn":
                _print_learn(obj)
                continue
            if obj.get("type") == "error":
                reason = obj.get("reason", "unknown")
                if reason == "no speech":
                    raise RuntimeError(
                        "bridge: no clear speech (too quiet). Try speaking louder."
                    )
                if reason == "asleep":
                    raise RuntimeError(
                        f"bridge: asleep — say {WAKE_LABEL} or press Enter to wake."
                    )
                if reason == "enroll_too_short":
                    raise RuntimeError(
                        f"bridge: wake phrase too short — say {WAKE_LABEL} clearly."
                    )
                if reason == "not your voice":
                    extra = ""
                    foc = obj.get("focus") or {}
                    m = foc.get("match")
                    if m is not None:
                        extra = f" (match={m})"
                    gate = foc.get("gate") or ""
                    if gate == "wake":
                        raise RuntimeError(
                            "bridge: not your voice — wake clip did not match you"
                            f"{extra}. Wait for the Asleep line, then say {WAKE_LABEL} "
                            "yourself (a friend's wake is supposed to fail)."
                        )
                    hint = (
                        f" Speak clearly after {WAKE_LABEL}; press Enter when done."
                    )
                    if foc.get("follow_up"):
                        hint = (
                            f" Same-session follow-up — say {WAKE_LABEL} again, "
                            "then your sentence."
                        )
                    raise RuntimeError(
                        "bridge: not your voice — your sentence did not match enroll"
                        f"{extra}.{hint}"
                    )
                if reason == "need_enroll":
                    raise RuntimeError(
                        "bridge: owner voice not enrolled. Run once:\n"
                        "  cd server\n"
                        "  C:\\Python314\\python.exe tools\\enroll_owner.py"
                    )
                if reason == "too_mixed":
                    raise RuntimeError(
                        "bridge: too much other speech in the clip. "
                        "Talk when others are quiet, move the mic closer, or press Enter "
                        "right after you finish (not while people are talking)."
                    )
                if reason == "spoof_suspected":
                    raise RuntimeError(SPOOF_SUSPECTED_MESSAGE)
                if reason == "tts_unavailable":
                    raise RuntimeError(_tts_unavailable_message(obj))
                raise RuntimeError(f"bridge error: {reason}")
            if obj.get("type") == "volume":
                print(f"Playback volume adjust: gain={obj.get('gain')}")
            if obj.get("type") == "stop":
                barged = True
                print("Playback stopped (barge).")
                continue
            if obj.get("type") == "busy":
                raise RuntimeError("bridge busy — wait and try again")
        else:
            out.extend(msg)

    try:
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
            if isinstance(msg, str):
                obj = json.loads(msg)
                if obj.get("type") == "learn":
                    _print_learn(obj)
                else:
                    break
            else:
                out.extend(msg)
    except asyncio.TimeoutError:
        pass

    return bytes(out), done


def play_pcm(pcm: bytes, ws=None, loop=None, *, allow_barge: bool = LAPTOP_BARGE) -> None:
    if not pcm:
        print("Nothing to play.")
        return
    samples = np.frombuffer(pcm, dtype=np.int16)
    print(f"Playing {len(samples) / SAMPLE_RATE:.1f}s…")
    sd.play(samples, SAMPLE_RATE)
    sd.wait()
    print("Finished playing.")


def _build_wake(hello: dict) -> WakeDetector:
    fc = hello.get("focus") or {}
    models_dir = ROOT / "models"
    custom = models_dir / "hey_astra.onnx"
    path = custom if custom.is_file() else None
    name = str(fc.get("wake_model", "hey_jarvis"))
    if path is not None:
        path = custom
        name = "hey_astra"
    return WakeDetector(
        model_path=path,
        model_name=name.replace("models/", "").replace(".onnx", ""),
        phrase=str(fc.get("wake_phrase", "hey astra")),
        threshold=float(fc.get("wake_threshold", 0.5)),
    )


async def session(uri: str, once: bool, *, noisy: bool = False) -> None:
    global ECHO_GUARD_MS, FOCUS_LOCK_OWNER, WAKE_LABEL, MAX_SEC
    global END_SILENCE_MS, MERGE_GAP_MS, SMART_TURN_WEIGHTS, FALLBACK_END_SILENCE_MS
    if noisy:
        ECHO_GUARD_MS = 1400
    global END_SILENCE_MS, MERGE_GAP_MS, FOCUS_ARMED, FOCUS_ENABLED, WAKE_READY
    global VAD_THRESHOLD, MIN_SPEECH_MS, NOISY_ROOM
    NOISY_ROOM = noisy
    loop = asyncio.get_running_loop()
    async with websockets.connect(
        uri,
        open_timeout=5,
        ping_interval=20,
        ping_timeout=300,
    ) as ws:
        hello_out: dict = {"type": "hello", "proto": 1, "fw": "laptop"}
        client_token = os.environ.get("ASTRA_CLIENT_TOKEN", "").strip()
        if client_token:
            hello_out["token"] = client_token
        await ws.send(json.dumps(hello_out))
        hello = json.loads(await ws.recv())
        print("Connected:", hello)
        tts_info = hello.get("tts") if isinstance(hello.get("tts"), dict) else {}
        voice_on = bool(tts_info.get("enabled"))
        voice_warning = _hello_voice_warning(hello)
        if voice_warning:
            print(voice_warning)
        FOCUS_ENABLED = bool((hello.get("focus") or {}).get("enabled"))
        WAKE_READY = bool((hello.get("focus") or {}).get("wake_ready"))
        wake = _build_wake(hello)
        WAKE_LABEL = _wake_label_from_phrase(wake.phrase)
        vad = hello.get("vad") or {}
        VAD_THRESHOLD = float(vad.get("threshold", 0.5))
        MIN_SPEECH_MS = int(vad.get("min_speech_ms", 280))
        fc = hello.get("focus") or {}
        FOCUS_LOCK_OWNER = bool(fc.get("lock_owner"))
        if FOCUS_ENABLED:
            if not fc.get("owner_enroll_complete") and fc.get("require_owner_enroll"):
                print(
                    "Focus ON — enroll your voice first:\n"
                    "  C:\\Python314\\python.exe tools\\enroll_owner.py  (from server folder)"
                )
            elif WAKE_READY or wake.wake_ready():
                print(f"Focus ON — say {WAKE_LABEL} to wake.")
                note = _stand_in_wake_note(wake)
                if note:
                    print(note)
            else:
                print("Focus ON — press Enter only if wake model missing.")
        lim = hello.get("limits") or {}
        if lim.get("max_clip_s"):
            MAX_SEC = int(lim["max_clip_s"])
        listen = hello.get("listen") or {}
        if listen.get("smart_turn_weights"):
            SMART_TURN_WEIGHTS = str(listen["smart_turn_weights"])
        if listen.get("fallback_end_silence_ms"):
            FALLBACK_END_SILENCE_MS = int(listen["fallback_end_silence_ms"])
        if listen.get("complete_close_ms"):
            COMPLETE_CLOSE_MS = int(listen["complete_close_ms"])
        if lim.get("pause_hold_ms") and not listen.get("fallback_end_silence_ms"):
            END_SILENCE_MS = int(lim["pause_hold_ms"])
            MERGE_GAP_MS = int(lim["pause_hold_ms"])
        elif listen.get("fallback_end_silence_ms"):
            END_SILENCE_MS = FALLBACK_END_SILENCE_MS
            MERGE_GAP_MS = FALLBACK_END_SILENCE_MS

        if wake.uses_kws():
            print("Loading Hey Astra listener…", flush=True)
            loaded = await asyncio.to_thread(wake.preload)
            if loaded:
                print("Listener ready.", flush=True)
            else:
                print("Wake model unavailable; press Enter to wake.", flush=True)

        first = True
        while True:
            wake_turn = False
            wake_pcm = b""
            wake_ms = 0
            enter_wake = False
            if FOCUS_ENABLED and (not FOCUS_ARMED or FOCUS_LOCK_OWNER):
                _ok, wake_pcm, wake_ms, enter_wake = await asyncio.to_thread(
                    _wait_for_wake, wake
                )
                wake_turn = True

            arm_delay = 0 if first else ECHO_GUARD_MS
            pcm_in = await asyncio.to_thread(
                record_one_utterance,
                vad_threshold=VAD_THRESHOLD,
                min_speech_ms=MIN_SPEECH_MS,
                arm_delay_ms=arm_delay,
                noisy_room=NOISY_ROOM,
            )
            first = False
            if not pcm_in:
                print("Too short — try again.")
            else:
                try:
                    pcm_out, done = await send_utterance(
                        ws,
                        pcm_in,
                        wake=wake_turn,
                        wake_pcm=wake_pcm if wake_pcm else None,
                        wake_speech_ms=wake_ms,
                        enter_wake=enter_wake,
                    )
                    if wake_turn and done.get("type") == "done" and not enter_wake:
                        FOCUS_ARMED = True
                    if enter_wake and done.get("type") == "done":
                        FOCUS_ARMED = True
                    _print_turn_summary(done, voice=voice_on)
                    if pcm_out:
                        await asyncio.to_thread(play_pcm, pcm_out, ws, loop)
                        await asyncio.sleep(ECHO_GUARD_MS / 1000.0)
                    elif done.get("barged"):
                        print(_no_audio_message(voice_on, barged=True))
                    else:
                        print(_no_audio_message(voice_on, barged=False))
                except RuntimeError as exc:
                    print(exc)
                    if "too_mixed" in str(exc):
                        FOCUS_ARMED = True
                    if "not your voice" in str(exc) or "asleep" in str(exc) or "enroll" in str(exc):
                        FOCUS_ARMED = False
            if once:
                break
            print("\n--- Ready ---\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Laptop mic → bridge → laptop speakers")
    p.add_argument("--uri", default="ws://127.0.0.1:8765")
    p.add_argument("--once", action="store_true", help="One utterance then exit")
    p.add_argument("--barge", action="store_true")
    p.add_argument(
        "--noisy",
        action="store_true",
        help="Stricter VAD for background chatter; press Enter when done speaking",
    )
    p.add_argument("--list-devices", action="store_true")
    args = p.parse_args()

    if args.list_devices:
        print(sd.query_devices())
        return

    global LAPTOP_BARGE
    if args.barge:
        LAPTOP_BARGE = True

    load_dotenv()
    try:
        asyncio.run(session(args.uri, args.once, noisy=args.noisy))
    except KeyboardInterrupt:
        print("\nBye.")
    except (OSError, TimeoutError, ConnectionRefusedError) as exc:
        raise SystemExit(
            f"Cannot reach {args.uri}\nStart the bridge first:  python bridge.py\nDetails: {exc}"
        ) from exc


if __name__ == "__main__":
    main()
