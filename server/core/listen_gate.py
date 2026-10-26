"""Decide when one spoken sentence is finished.

A pause of about half a second to one second is still the same sentence.
The mic stays open until silence lasts pause_hold_ms (default 2 seconds).
"""

from __future__ import annotations

from collections import deque


def pause_hold_ms(end_silence_ms: int, merge_gap_ms: int) -> int:
    """How long quiet must last before the sentence is over."""
    return max(int(end_silence_ms), int(merge_gap_ms), 1)


class UtteranceGate:
    def __init__(
        self,
        *,
        frame_ms: int = 20,
        min_speech_ms: int = 250,
        end_silence_ms: int = 2000,
        max_ms: int = 15000,
        preroll_ms: int = 300,
        silence_break_frames: int = 4,
    ) -> None:
        self.frame_ms = frame_ms
        self.min_speech_frames = max(1, (min_speech_ms + frame_ms - 1) // frame_ms)
        self.end_silence_frames = max(1, end_silence_ms // frame_ms)
        self.max_frames = max(1, max_ms // frame_ms)
        self.silence_break_frames = max(1, silence_break_frames)
        self.preroll: deque[bytes] = deque(maxlen=max(1, preroll_ms // frame_ms))
        self.pcm = bytearray()
        self.speech_run = 0
        self.silence_run = 0
        self.speech_run_end = 0
        self.capturing = False
        self.frames = 0
        self.closed = False
        self.hit_max = False

    def push(self, is_speech: bool, frame: bytes) -> str:
        """Return wait, open, hold, closed, or max."""
        if self.closed:
            return "closed"

        if not self.capturing:
            self.preroll.append(frame)
            if is_speech:
                self.speech_run += 1
                if self.speech_run >= self.min_speech_frames:
                    self.capturing = True
                    self.silence_run = 0
                    for chunk in self.preroll:
                        self.pcm.extend(chunk)
                    self.frames = len(self.preroll)
                    self.preroll.clear()
                    return "open"
            else:
                self.speech_run = 0
            return "wait"

        self.pcm.extend(frame)
        self.frames += 1
        if self.frames >= self.max_frames:
            self.closed = True
            self.hit_max = True
            return "max"
        if is_speech:
            self.speech_run_end += 1
            if self.speech_run_end >= self.silence_break_frames:
                self.silence_run = 0
            return "open"
        self.speech_run_end = 0
        self.silence_run += 1
        if (
            self.silence_run >= self.end_silence_frames
            and self.frames > self.min_speech_frames
        ):
            return "pause_check"
        return "hold"

    def defer_close(self) -> None:
        """User may still be thinking — keep the mic open."""
        self.silence_run = 0

    def mark_turn_complete(self) -> None:
        self.closed = True

    def finish_now(self) -> None:
        """User pressed Enter — end capture even if VAD still hears room noise."""
        if self.capturing and self.frames > self.min_speech_frames:
            self.closed = True
