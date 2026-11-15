"""Tests for the pure analysis and scoring functions."""

import math

from custom_components.bed_sleep_score.scoring import NightInputs, compute_score, ema, magnitude, std_dev


def test_reference_night() -> None:
    """A real reference night: 30 + 21 + 13 + 10 + 10 = 84."""
    result = compute_score(
        NightInputs(continuity_min=166, movements=10, clusters=4, samples=500, mean=0.020, minimum=0.008, maximum=0.25)
    )
    assert result["components"] == {
        "continuity": 30.0,
        "movements": 20.8,
        "wakeups": 13.3,
        "calm": 10.0,
        "intensity": 10.0,
    }
    assert result["score"] == 84
    assert not result["neutral_signal"]


def test_perfect_night() -> None:
    result = compute_score(
        NightInputs(continuity_min=300, movements=4, clusters=0, samples=500, mean=0.010, minimum=0.006, maximum=0.2)
    )
    assert result["score"] == 100


def test_bad_night() -> None:
    result = compute_score(
        NightInputs(continuity_min=25, movements=30, clusters=12, samples=500, mean=0.05, minimum=0.01, maximum=5.0)
    )
    assert result["score"] == 0


def test_neutral_fallback_without_signal() -> None:
    result = compute_score(NightInputs(continuity_min=120, movements=8, clusters=2, samples=3))
    assert result["neutral_signal"]
    assert result["components"]["calm"] == 7.5
    assert result["components"]["intensity"] == 5
    assert result["score"] == 88  # 30 + 25 + 20 + 7.5 + 5 = 87.5


def test_linear_components() -> None:
    result = compute_score(NightInputs(continuity_min=75, movements=14, clusters=5))
    assert result["components"]["continuity"] == 15.0
    assert result["components"]["movements"] == 12.5
    assert result["components"]["wakeups"] == 10.0


def test_scale_follows_threshold() -> None:
    """With a 10x threshold the calm and intensity anchors are 10x too."""
    night = NightInputs(
        continuity_min=120, movements=0, clusters=0, samples=50, mean=0.24, minimum=0.1, maximum=math.sqrt(3 * 30)
    )
    result = compute_score(night, scale=10)
    assert result["components"]["calm"] == 7.5
    assert result["components"]["intensity"] == 5.0
    assert compute_score(night)["components"]["calm"] == 0


def test_signal_helpers() -> None:
    assert magnitude([3.0]) == 3.0
    assert magnitude([3.0, 4.0, 12.0]) == 13.0
    assert std_dev([1.0]) is None
    assert round(std_dev([2, 4, 4, 4, 5, 5, 7, 9]), 4) == 2.1381
    assert ema(None, 80, 0.25) == 80
    assert ema(80, 100, 0.25) == 85.0
