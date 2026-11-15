# SPDX-License-Identifier: GPL-3.0-or-later
"""Signal analysis and sleep score formula (v3).

Pure functions with no Home Assistant dependency, so they can be unit tested
in isolation. The score is the sum of five components (0-100):

1. Continuity (30 pt) - longest undisturbed stretch between two movements,
   window edges included. >= 120 min (about one complete 90-110 min sleep
   cycle) gives full points, <= 30 min gives zero, linear in between.
2. Movements (25 pt) - movement episodes in the window: up to 8 are free, zero
   points at 20. Video studies count 12-20 posture changes per night in
   healthy sleepers, doubling in poor sleepers (Cary et al., PLOS ONE 2021);
   a bed accelerometer only sees the larger ones, roughly half.
3. Wake-ups (20 pt) - "clustered" movements, i.e. a movement less than 15
   minutes after the previous one, the first of the night excluded: a burst of
   movements is the signature of an awakening. Up to 2 are free, zero at 8.
   The National Sleep Foundation consensus (Ohayon et al., Sleep Health 2017)
   rates <= 1 awakening > 5 min as good sleep and >= 4 as poor.
4. Calm (15 pt) - net agitation = mean - minimum of the signal over the window
   (immune to constant offsets such as fans or the sensor noise floor).
5. Intensity (10 pt) - peak agitation of the night on a log10 scale. Movement
   intensity correlates with autonomic activation (Sicbaldi et al.,
   Sci Rep 2025).

Calm and intensity fall back to neutral values (half points) when not enough
signal samples were collected during the window. ``scale`` stretches the calm
and intensity anchors together with the movement threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .const import (
    CALM_FULL,
    CALM_ZERO,
    CLUSTERS_ZERO_AT,
    CONTINUITY_FULL_MIN,
    CONTINUITY_ZERO_MIN,
    FREE_CLUSTERS,
    FREE_MOVEMENTS,
    MAX_POINTS,
    MIN_NIGHT_SAMPLES,
    MOVEMENTS_ZERO_AT,
    PEAK_FULL,
    PEAK_ZERO,
)


def magnitude(axes: list[float]) -> float:
    """Acceleration magnitude from one to three axes (one value passes through)."""
    if len(axes) == 1:
        return axes[0]
    return math.sqrt(sum(value * value for value in axes))


def std_dev(values: list[float]) -> float | None:
    """Sample standard deviation (n-1)."""
    count = len(values)
    if count < 2:
        return None
    mean = sum(values) / count
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (count - 1))


def ema(previous: float | None, value: float, alpha: float) -> float:
    """Exponential moving average; seeds with the first value."""
    if previous is None or previous <= 0:
        return float(value)
    return round(previous + alpha * (value - previous), 1)


@dataclass(slots=True)
class NightInputs:
    """Raw measurements of one night."""

    continuity_min: float
    movements: int
    clusters: int
    samples: int = 0
    mean: float | None = None
    minimum: float | None = None
    maximum: float | None = None


def _linear(value: float, zero_at: float, full_at: float, points: float) -> float:
    """Points growing linearly from ``zero_at`` (0) to ``full_at`` (all)."""
    ratio = (value - zero_at) / (full_at - zero_at)
    return round(points * max(0.0, min(1.0, ratio)), 1)


def compute_score(night: NightInputs, scale: float = 1.0) -> dict[str, Any]:
    """Compute the 0-100 sleep score of one night."""
    has_signal = night.samples >= MIN_NIGHT_SAMPLES and None not in (night.mean, night.minimum, night.maximum)
    net = max(night.mean - night.minimum, 0.0) if has_signal else None
    peak = night.maximum if has_signal and night.maximum > 0 else None

    components = {
        "continuity": _linear(night.continuity_min, CONTINUITY_ZERO_MIN, CONTINUITY_FULL_MIN, MAX_POINTS["continuity"]),
        "movements": _linear(night.movements, MOVEMENTS_ZERO_AT, FREE_MOVEMENTS, MAX_POINTS["movements"]),
        "wakeups": _linear(night.clusters, CLUSTERS_ZERO_AT, FREE_CLUSTERS, MAX_POINTS["wakeups"]),
        "calm": MAX_POINTS["calm"] / 2
        if net is None
        else _linear(net, CALM_ZERO * scale, CALM_FULL * scale, MAX_POINTS["calm"]),
        "intensity": MAX_POINTS["intensity"] / 2
        if peak is None
        else _linear(
            math.log10(peak),
            math.log10(PEAK_ZERO * scale),
            math.log10(PEAK_FULL * scale),
            MAX_POINTS["intensity"],
        ),
    }
    return {
        "score": max(0, min(100, round(sum(components.values())))),
        "components": components,
        "net_agitation": round(net, 5) if net is not None else None,
        "peak_agitation": round(peak, 5) if peak is not None else None,
        "neutral_signal": not has_signal,
    }
