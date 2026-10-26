from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.doa import (  # noqa: E402
    delay_samples_to_azimuth_deg,
    estimate_azimuth_from_stereo_pcm,
)
from tests.fixtures.stereo_pcm import (  # noqa: E402
    noise_burst_pcm16,
    stereo_pcm_with_left_delay,
    stereo_pcm_with_right_delay,
)

SAMPLE_RATE = 16000
# Wider spacing keeps test delays in a stable part of asin().
TEST_MIC_SPACING_M = 0.14
AZIMUTH_TOL_DEG = 12.0


@pytest.mark.parametrize("delay_samples", [2, 4, 6])
def test_synthetic_stereo_azimuth_within_tolerance(delay_samples: int) -> None:
    mono = noise_burst_pcm16(SAMPLE_RATE, seconds=0.3, seed=100 + delay_samples)
    pcm = stereo_pcm_with_right_delay(mono, delay_samples)
    expected = delay_samples_to_azimuth_deg(
        delay_samples, SAMPLE_RATE, TEST_MIC_SPACING_M
    )
    got = estimate_azimuth_from_stereo_pcm(
        pcm, SAMPLE_RATE, mic_spacing_m=TEST_MIC_SPACING_M
    )
    assert got is not None
    assert abs(got - expected) <= AZIMUTH_TOL_DEG


def test_negative_azimuth_when_left_lags() -> None:
    """Left delayed vs right ⇒ source to the right (negative azimuth)."""
    mono = noise_burst_pcm16(SAMPLE_RATE, seconds=0.3, seed=7)
    delay = 3
    pcm = stereo_pcm_with_left_delay(mono, delay)
    expected = -delay_samples_to_azimuth_deg(
        delay, SAMPLE_RATE, TEST_MIC_SPACING_M
    )
    got = estimate_azimuth_from_stereo_pcm(
        pcm, SAMPLE_RATE, mic_spacing_m=TEST_MIC_SPACING_M
    )
    assert got is not None
    assert abs(got - expected) <= AZIMUTH_TOL_DEG


def test_too_short_returns_none() -> None:
    pcm = stereo_pcm_with_right_delay(noise_burst_pcm16(SAMPLE_RATE, 0.05), 2)
    assert (
        estimate_azimuth_from_stereo_pcm(
            pcm, SAMPLE_RATE, mic_spacing_m=TEST_MIC_SPACING_M
        )
        is None
    )
