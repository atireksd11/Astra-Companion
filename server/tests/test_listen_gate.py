from core.listen_gate import UtteranceGate, pause_hold_ms

FRAME = b"\x01\x00" * 320


def test_pause_hold_uses_the_longer_gap() -> None:
    assert pause_hold_ms(1200, 2000) == 2000
    assert pause_hold_ms(2000, 1500) == 2000


def test_one_second_pause_keeps_the_next_phrase() -> None:
    """hello, ~1s quiet, more words — still one clip."""
    gate = UtteranceGate(min_speech_ms=100, end_silence_ms=2000, preroll_ms=100)
    for _ in range(10):
        assert gate.push(True, FRAME) in ("wait", "open")
    assert gate.capturing
    for _ in range(50):  # 1.0 s
        assert gate.push(False, FRAME) == "hold"
    for _ in range(10):
        assert gate.push(True, FRAME) == "open"
    for _ in range(100):
        status = gate.push(False, FRAME)
    assert status == "pause_check"
    gate.mark_turn_complete()
    assert gate.closed
    assert len(gate.pcm) > len(FRAME) * 60


def test_preroll_is_not_thrown_away() -> None:
    gate = UtteranceGate(min_speech_ms=60, end_silence_ms=200, preroll_ms=100)
    quiet = b"\x00\x00" * 320
    gate.push(False, quiet)
    gate.push(False, quiet)
    gate.push(True, FRAME)
    gate.push(True, FRAME)
    gate.push(True, FRAME)
    assert gate.capturing
    assert quiet in gate.pcm
    assert FRAME in gate.pcm


def test_finish_now_closes_when_user_hits_enter() -> None:
    gate = UtteranceGate(min_speech_ms=60, end_silence_ms=5000, frame_ms=32)
    for _ in range(8):
        gate.push(True, FRAME)
    assert gate.capturing
    gate.finish_now()
    assert gate.closed
