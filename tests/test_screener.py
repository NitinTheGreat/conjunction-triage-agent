"""Regression tests for the close-approach screener's candidate selection.

The defect
----------
``screen_pair`` used to reject candidate intervals on **sampled** distance::

    candidates = [i for i in interior if ranges[i] < threshold_km * 5]

The sampled minimum is not a bound on the true minimum. At 60 s spacing and 14 km/s a
crossing can sit at zero separation midway between two samples that both read 420 km, and
a 5x cutoff on a 10 km screen discards it. The screen then reports no conjunction where
one exists, which is the one failure mode a screener may not have.

The counterexample is reproduced here first, on the selection logic where the bug lived,
so the fix is demonstrably fixing something rather than merely present.

Why the fix is a bound and not a finer step
-------------------------------------------
Halving the step does not make the search complete — it makes the same unsound argument at
a smaller scale, and there is always a crossing fast enough to hide between two samples.
The replacement rejects an interval only when a *rigorous* lower bound on separation over
the whole interval exceeds the threshold, so a rejection is a proof rather than a hope.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from orbital.propagate import (
    REFERENCE_CASE,
    candidate_indices,
    candidate_intervals,
    max_relative_speed_over_interval,
    propagate_series,
    screen_pair,
    swept_separation_lower_bound,
)

#: Two objects on the same orbit with a 1 degree RAAN offset, phased to meet. The oracle
#: below establishes the truth for this pair; nothing here trusts the screener for it.
CROSSING_TLE_1 = (REFERENCE_CASE["line1"], REFERENCE_CASE["line2"])
CROSSING_TLE_2 = (
    REFERENCE_CASE["line1"],
    "2 88888  72.8435 116.9689 0086731  52.6988 110.3214 16.05824518   105",
)
WINDOW_START = datetime(1980, 10, 1, 23, 41, 24, tzinfo=timezone.utc)
WINDOW_STOP = WINDOW_START + timedelta(minutes=95)


def _old_prefilter(ranges: np.ndarray, threshold_km: float) -> list[int]:
    """The rejected implementation, kept so the counterexample can be shown to bite."""
    interior = np.flatnonzero(
        (ranges[1:-1] <= ranges[:-2]) & (ranges[1:-1] <= ranges[2:])
    ) + 1
    return [int(i) for i in interior if ranges[i] < threshold_km * 5]


# -- the counterexample --------------------------------------------------------------------


def test_the_old_prefilter_discards_a_real_crossing():
    """The audit's scenario, with its numbers: 0 km at 30 s, 420 km at both samples."""
    ranges = np.array([1200.0, 420.0, 420.0, 1200.0])
    assert _old_prefilter(ranges, threshold_km=10.0) == [], (
        "the old prefilter no longer discards the counterexample; the regression it "
        "guards has changed shape"
    )


def test_the_swept_bound_keeps_that_crossing():
    ranges = np.array([1200.0, 420.0, 420.0, 1200.0])
    speeds = np.full(4, 14.0)
    radii = np.full(4, 7000.0)
    kept = candidate_indices(ranges, speeds, radii, step_seconds=60.0, threshold_km=10.0)
    assert kept, "the swept bound discarded an interval that can reach zero separation"
    assert 1 in kept and 2 in kept


def test_the_bound_is_zero_when_the_pair_can_close_completely():
    speed = max_relative_speed_over_interval(14.0, 14.0, 7000.0, 60.0)
    assert swept_separation_lower_bound(420.0, 420.0, speed, 60.0) == 0.0


# -- soundness: the bound must never exceed the truth ---------------------------------------


def test_the_bound_never_exceeds_the_true_minimum():
    """Rejecting on the bound is only sound if the bound is a genuine lower bound.

    Checked against straight-line relative motion, for which the minimum separation is
    known exactly, over a wide sweep of speeds, step lengths, offsets and miss distances.
    """
    rng = np.random.default_rng(3)
    worst = 0.0
    for _ in range(5000):
        speed = rng.uniform(0.5, 16.0)
        step = rng.uniform(1.0, 300.0)
        closest_at = rng.uniform(-1.0, 1.0) * step
        miss = rng.uniform(0.0, 50.0)

        times = np.linspace(0.0, step, 2001)
        true_minimum = float(np.min(np.hypot(miss, speed * (times - closest_at))))
        range_a = float(np.hypot(miss, speed * (0.0 - closest_at)))
        range_b = float(np.hypot(miss, speed * (step - closest_at)))
        bound = swept_separation_lower_bound(range_a, range_b, speed, step)
        worst = max(worst, bound - true_minimum)

    assert worst < 1e-9, f"the bound exceeded the true minimum by {worst:.3e} km"


def test_a_pair_that_genuinely_cannot_close_is_still_rejected():
    """The bound must not be so loose that it keeps everything.

    Two samples 5,000 km apart at 1 km/s over 60 s cannot approach within 10 km, and the
    screener should say so rather than refine a hopeless interval.
    """
    ranges = np.array([5000.0, 5000.0])
    speeds = np.full(2, 1.0)
    radii = np.full(2, 7000.0)
    assert candidate_intervals(ranges, speeds, radii, 60.0, 10.0) == []


def test_rejection_rate_is_useful_on_a_real_pair():
    """A bound that never rejects is correct and worthless. This one still prunes."""
    first = propagate_series(*CROSSING_TLE_1, WINDOW_START, WINDOW_STOP, 60.0, "a")
    second = propagate_series(*CROSSING_TLE_2, WINDOW_START, WINDOW_STOP, 60.0, "b")
    ranges = np.array([np.linalg.norm(a.position - b.position) for a, b in zip(first, second)])
    speeds = np.array([np.linalg.norm(a.velocity - b.velocity) for a, b in zip(first, second)])
    radii = np.array([
        min(np.linalg.norm(a.position), np.linalg.norm(b.position))
        for a, b in zip(first, second)
    ])
    kept = candidate_intervals(ranges, speeds, radii, 60.0, 10.0)
    assert 0 < len(kept) < len(ranges) - 1, (
        f"kept {len(kept)} of {len(ranges) - 1} intervals; a useful bound prunes some "
        "and keeps the real crossing"
    )


# -- against a brute-force oracle ----------------------------------------------------------


@pytest.mark.parametrize("coarse_step", [60.0, 300.0, 600.0])
def test_screener_matches_a_fine_step_oracle(coarse_step):
    """The corrected screener finds what a 1-second sweep finds, at every coarse step.

    The oracle is brute force over the same window: no shared code path with the screener's
    candidate selection, so agreement is evidence rather than tautology.
    """
    first = propagate_series(*CROSSING_TLE_1, WINDOW_START, WINDOW_STOP, 1.0, "a")
    second = propagate_series(*CROSSING_TLE_2, WINDOW_START, WINDOW_STOP, 1.0, "b")
    separations = np.array([
        np.linalg.norm(a.position - b.position) for a, b in zip(first, second)
    ])
    oracle_minimum = float(separations.min())
    assert oracle_minimum < 10.0, "the fixture pair no longer has a close approach"

    found = screen_pair(
        CROSSING_TLE_1, CROSSING_TLE_2, WINDOW_START, WINDOW_STOP,
        threshold_km=10.0, coarse_step_seconds=coarse_step, refine_step_seconds=0.5,
    )
    assert found, f"screener found nothing at {coarse_step} s; the oracle found {oracle_minimum:.4f} km"
    assert min(a.miss_distance_km for a in found) == pytest.approx(oracle_minimum, abs=0.05)


def test_self_conjunction_still_works():
    """The degenerate case the Phase 9 suite already covered must not regress."""
    approaches = screen_pair(
        CROSSING_TLE_1, CROSSING_TLE_1, WINDOW_START, WINDOW_START + timedelta(minutes=20),
        threshold_km=1.0, coarse_step_seconds=60.0, refine_step_seconds=5.0,
    )
    assert approaches
    assert approaches[0].miss_distance_km == pytest.approx(0.0, abs=1e-9)
