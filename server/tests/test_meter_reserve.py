from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.meter import Meter  # noqa: E402


def test_try_reserve_respects_cap(tmp_path: Path) -> None:
    m = Meter(tmp_path / "m.db", daily_cap_usd=0.10)
    assert m.try_reserve(0.05)
    assert m.try_reserve(0.04)
    assert not m.try_reserve(0.02)
    assert m.today_usd() == pytest.approx(0.09, abs=1e-6)


def test_settle_adjusts_reserved_to_actual(tmp_path: Path) -> None:
    m = Meter(tmp_path / "m.db", daily_cap_usd=1.0)
    assert m.try_reserve(0.05)
    m.settle(0.05, 0.03)
    assert m.today_usd() == pytest.approx(0.03, abs=1e-6)


def test_settle_releases_failed_turn_reserve(tmp_path: Path) -> None:
    m = Meter(tmp_path / "m.db", daily_cap_usd=1.0)
    assert m.try_reserve(0.04)
    m.settle(0.04, 0.0)
    assert m.today_usd() == pytest.approx(0.0, abs=1e-6)
