"""Phoneme alignment interface (feature 8). v1: null backend only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PhoneSpan:
    phone: str
    start_ms: float
    end_ms: float


@dataclass
class WordAlignment:
    word: str
    phones: list[PhoneSpan]


class Aligner(Protocol):
    def align(self, pcm: bytes, rate: int, words: list[str]) -> list[WordAlignment]: ...


class NullAligner:
    def align(self, pcm: bytes, rate: int, words: list[str]) -> list[WordAlignment]:
        return []
