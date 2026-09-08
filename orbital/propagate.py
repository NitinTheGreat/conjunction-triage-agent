"""Orbit propagation from TLEs via SGP4, and close-approach screening.

Uses Skyfield's SGP4 implementation. SGP4 is the propagator the TLE format is *defined*
against — a TLE is a set of mean elements that only means anything when fed through SGP4 —
so this is the correct pairing rather than a convenience.

Verification
------------
:func:`verify_reference_case` propagates a published TLE to a published state and reports
the residual, so the propagation path is checked rather than assumed. The reference is the
Vallado et al. SGP4 test case, which ships with the ``sgp4`` package's own test suite.

Offline by construction
-----------------------
Nothing here fetches a TLE. Callers supply the two lines. That keeps the module usable when
CelesTrak is unreachable, which it is from this host (constraint 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional, Sequence

import numpy as np

__all__ = [
    "PropagationError",
    "swept_separation_lower_bound",
    "max_relative_speed_over_interval",
    "candidate_intervals",
    "candidate_indices",
    "StateVector",
    "CloseApproach",
    "propagate_tle",
    "propagate_series",
    "screen_pair",
    "verify_reference_case",
    "REFERENCE_CASE",
]


class PropagationError(RuntimeError):
    """Raised when propagation fails. Never returns a placeholder state."""


@dataclass(frozen=True)
class StateVector:
    """A position and velocity in TEME at one instant.

    SGP4 natively produces **TEME** (True Equator Mean Equinox), not J2000/ECI. The two
    differ by a small rotation (arcseconds to arcminutes over the TLE's validity window).
    That difference is recorded here rather than silently ignored; see
    :func:`propagate_tle` for what it means for Pc.
    """

    epoch_utc: datetime
    position_km: tuple[float, float, float]
    velocity_kms: tuple[float, float, float]
    frame: str = "TEME"

    @property
    def position(self) -> np.ndarray:
        return np.array(self.position_km, dtype=np.float64)

    @property
    def velocity(self) -> np.ndarray:
        return np.array(self.velocity_kms, dtype=np.float64)

    @property
    def altitude_km(self) -> float:
        """Spherical altitude above a 6378.137 km Earth. Not geodetic."""
        return float(np.linalg.norm(self.position)) - 6378.137


@dataclass(frozen=True)
class CloseApproach:
    """One local minimum of the range between two objects."""

    tca_utc: datetime
    miss_distance_km: float
    relative_speed_kms: float
    state1: StateVector
    state2: StateVector

    def as_dict(self) -> dict[str, object]:
        return {
            "tca_utc": self.tca_utc.isoformat(),
            "miss_distance_km": self.miss_distance_km,
            "relative_speed_kms": self.relative_speed_kms,
            "object1": {
                "position_km": list(self.state1.position_km),
                "velocity_kms": list(self.state1.velocity_kms),
                "altitude_km": self.state1.altitude_km,
            },
            "object2": {
                "position_km": list(self.state2.position_km),
                "velocity_kms": list(self.state2.velocity_kms),
                "altitude_km": self.state2.altitude_km,
            },
            "frame": self.state1.frame,
        }


#: The Vallado SGP4 verification case (satellite 88888), from the sgp4 package's own tests.
#: Propagating this TLE 360 minutes past epoch has a published answer, so the residual is a
#: real check on the propagation path rather than a self-consistency test.
REFERENCE_CASE = {
    "name": "Vallado SGP4 test case, satellite 88888",
    "line1": "1 88888U          80275.98708465  .00073094  13844-3  66816-4 0     8",
    "line2": "2 88888  72.8435 115.9689 0086731  52.6988 110.5714 16.05824518   105",
    "minutes_after_epoch": 360.0,
    # Read from the sgp4 package's own `tcppver.out`, the official Vallado verification
    # output, rather than transcribed from memory -- a first attempt at these constants
    # used values belonging to a different satellite and reported a 15,746 km residual
    # against a propagation that was in fact correct.
    "expected_position_km": (2456.10706533, -6071.93855503, 1222.89768554),
    "expected_velocity_kms": (2.679390040, -0.448290811, -7.228792155),
    "source": (
        "Vallado, Crawford, Hujsak & Kelso (2006), AIAA 2006-6753; values taken from "
        "sgp4/tcppver.out shipped with the sgp4 package"
    ),
    "tolerance_km": 1e-3,
}


def _load_satellite(line1: str, line2: str, name: str = "sat"):
    from sgp4.api import Satrec

    try:
        satellite = Satrec.twoline2rv(line1.strip(), line2.strip())
    except Exception as exc:
        raise PropagationError(f"{name}: TLE could not be parsed: {exc}") from exc
    return satellite


def propagate_tle(
    line1: str, line2: str, when_utc: datetime, name: str = "sat"
) -> StateVector:
    """Propagate one TLE to one instant. Raises on any SGP4 error code.

    The returned state is **TEME**. For conjunction geometry that is acceptable and is what
    operational screening does: the TEME-to-J2000 rotation is common to both objects, and Pc
    depends only on their *relative* position and velocity, which a shared rotation leaves
    unchanged. It matters only when mixing an SGP4 state with a state expressed in another
    frame, which this project never does.
    """
    from sgp4.api import SGP4_ERRORS, jday

    if when_utc.tzinfo is None:
        raise PropagationError("when_utc must be timezone-aware")
    moment = when_utc.astimezone(timezone.utc)

    satellite = _load_satellite(line1, line2, name)
    julian_day, fraction = jday(
        moment.year, moment.month, moment.day,
        moment.hour, moment.minute,
        moment.second + moment.microsecond / 1e6,
    )
    error, position, velocity = satellite.sgp4(julian_day, fraction)
    if error != 0:
        raise PropagationError(
            f"{name}: SGP4 error {error}: {SGP4_ERRORS.get(error, 'unknown')}"
        )
    if not all(np.isfinite(position)) or not all(np.isfinite(velocity)):
        raise PropagationError(f"{name}: SGP4 returned a non-finite state")

    return StateVector(
        epoch_utc=moment,
        position_km=(float(position[0]), float(position[1]), float(position[2])),
        velocity_kms=(float(velocity[0]), float(velocity[1]), float(velocity[2])),
    )


def propagate_series(
    line1: str, line2: str, start_utc: datetime, stop_utc: datetime,
    step_seconds: float, name: str = "sat",
) -> list[StateVector]:
    """Propagate a TLE across a window. Vectorised through SGP4's array interface."""
    from sgp4.api import SGP4_ERRORS, jday

    if stop_utc <= start_utc:
        raise PropagationError("stop_utc must be after start_utc")
    if step_seconds <= 0:
        raise PropagationError("step_seconds must be positive")

    total = (stop_utc - start_utc).total_seconds()
    count = int(total // step_seconds) + 1
    if count > 2_000_000:
        raise PropagationError(
            f"{count:,} steps requested; refusing to allocate. Widen step_seconds."
        )

    satellite = _load_satellite(line1, line2, name)
    moments = [start_utc + timedelta(seconds=i * step_seconds) for i in range(count)]
    days, fractions = zip(*(
        jday(m.year, m.month, m.day, m.hour, m.minute, m.second + m.microsecond / 1e6)
        for m in moments
    ))
    errors, positions, velocities = satellite.sgp4_array(
        np.array(days), np.array(fractions)
    )
    if np.any(errors != 0):
        first = int(np.flatnonzero(errors != 0)[0])
        code = int(errors[first])
        raise PropagationError(
            f"{name}: SGP4 error {code} at step {first} "
            f"({SGP4_ERRORS.get(code, 'unknown')})"
        )

    return [
        StateVector(
            epoch_utc=moment,
            position_km=(float(p[0]), float(p[1]), float(p[2])),
            velocity_kms=(float(v[0]), float(v[1]), float(v[2])),
        )
        for moment, p, v in zip(moments, positions, velocities)
    ]


def screen_pair(
    tle1: tuple[str, str], tle2: tuple[str, str],
    start_utc: datetime, stop_utc: datetime,
    threshold_km: float = 10.0,
    coarse_step_seconds: float = 60.0,
    refine_step_seconds: float = 0.5,
) -> list[CloseApproach]:
    """Find close approaches between two objects inside a window.

    Two-pass, which is how operational screening works: a coarse sweep locates local minima
    of the range, then each candidate is re-propagated finely to pin the time of closest
    approach. A single fine sweep over a week would be prohibitive; a single coarse sweep
    would misplace TCA by up to half a step, and at 14 km/s that is 7 km of error in the miss
    distance — larger than the screening threshold itself.
    """
    coarse1 = propagate_series(*tle1, start_utc, stop_utc, coarse_step_seconds, "object1")
    coarse2 = propagate_series(*tle2, start_utc, stop_utc, coarse_step_seconds, "object2")

    ranges = np.array([
        np.linalg.norm(a.position - b.position) for a, b in zip(coarse1, coarse2)
    ])
    if ranges.size < 3:
        raise PropagationError("window too short to identify a local minimum")

    speeds = np.array([
        np.linalg.norm(a.velocity - b.velocity) for a, b in zip(coarse1, coarse2)
    ])
    radii = np.array([
        min(np.linalg.norm(a.position), np.linalg.norm(b.position))
        for a, b in zip(coarse1, coarse2)
    ])
    candidates = candidate_indices(ranges, speeds, radii, coarse_step_seconds, threshold_km)

    approaches: list[CloseApproach] = []
    for index in candidates:
        window_start = coarse1[max(index - 1, 0)].epoch_utc
        window_stop = coarse1[min(index + 1, len(coarse1) - 1)].epoch_utc
        if window_stop <= window_start:
            continue

        fine1 = propagate_series(*tle1, window_start, window_stop, refine_step_seconds, "object1")
        fine2 = propagate_series(*tle2, window_start, window_stop, refine_step_seconds, "object2")
        fine_ranges = np.array([
            np.linalg.norm(a.position - b.position) for a, b in zip(fine1, fine2)
        ])
        best = int(np.argmin(fine_ranges))
        miss = float(fine_ranges[best])
        if miss > threshold_km:
            continue

        state1, state2 = fine1[best], fine2[best]
        approaches.append(CloseApproach(
            tca_utc=state1.epoch_utc,
            miss_distance_km=miss,
            relative_speed_kms=float(np.linalg.norm(state2.velocity - state1.velocity)),
            state1=state1,
            state2=state2,
        ))

    approaches.sort(key=lambda a: a.miss_distance_km)
    return approaches


#: Earth's gravitational parameter, km^3/s^2. Used only to bound relative acceleration.
MU_EARTH_KM3_S2 = 398600.4418


def swept_separation_lower_bound(
    range_a_km: float, range_b_km: float, max_relative_speed_kms: float,
    step_seconds: float,
) -> float:
    """A rigorous lower bound on separation *between* two samples.

    Separation is 1-Lipschitz in relative displacement, so over an interval of length
    ``dt`` with relative speed bounded by ``v``:

        r(t) >= r_a - v (t - t_a)      and      r(t) >= r_b - v (t_b - t)

    The tighter of the two is minimised where they cross, giving

        r_min >= max(0, (r_a + r_b - v dt) / 2)

    Nothing about the trajectory shape is assumed, so a pair rejected on this bound
    genuinely cannot approach within the threshold in the interval.
    """
    return max(0.0, 0.5 * (range_a_km + range_b_km - max_relative_speed_kms * step_seconds))


def max_relative_speed_over_interval(
    speed_a_kms: float, speed_b_kms: float, min_radius_km: float, step_seconds: float
) -> float:
    """Bound the relative speed across an interval from its endpoints.

    Relative speed can only change by the relative acceleration, and in Earth orbit each
    body's acceleration is at most ``mu / r^2``. Taking both bodies and the smaller radius
    seen at either endpoint gives a conservative envelope.
    """
    acceleration = 2.0 * MU_EARTH_KM3_S2 / max(min_radius_km, 1.0) ** 2
    return max(speed_a_kms, speed_b_kms) + acceleration * step_seconds


def candidate_intervals(
    ranges: np.ndarray, speeds: np.ndarray, radii: np.ndarray,
    step_seconds: float, threshold_km: float,
) -> list[int]:
    """Intervals ``[i, i+1]`` that could contain an approach within the threshold.

    Replaces a prefilter that rejected candidates on *sampled* distance. That was unsound:
    at 60 s spacing and 14 km/s a crossing can sit at zero separation between two samples
    that both read hundreds of kilometres, and a 5x cutoff on a 10 km screen discarded it.
    The sampled minimum is not a bound on the true minimum; this is.
    """
    keep = []
    for index in range(len(ranges) - 1):
        speed = max_relative_speed_over_interval(
            float(speeds[index]), float(speeds[index + 1]),
            float(min(radii[index], radii[index + 1])), step_seconds,
        )
        bound = swept_separation_lower_bound(
            float(ranges[index]), float(ranges[index + 1]), speed, step_seconds
        )
        if bound <= threshold_km:
            keep.append(index)
    return keep


def candidate_indices(
    ranges: np.ndarray, speeds: np.ndarray, radii: np.ndarray,
    step_seconds: float, threshold_km: float,
) -> list[int]:
    """Sample indices whose neighbourhood must be refined.

    Each surviving interval contributes its left endpoint; the refinement window in
    :func:`screen_pair` spans one coarse step either side, so an approach anywhere inside
    the interval is covered.
    """
    intervals = candidate_intervals(ranges, speeds, radii, step_seconds, threshold_km)
    return sorted({index for interval in intervals for index in (interval, interval + 1)})


def verify_reference_case() -> dict[str, object]:
    """Propagate the published reference TLE and report the residual against its answer."""
    from sgp4.api import Satrec

    case = REFERENCE_CASE
    satellite = Satrec.twoline2rv(case["line1"], case["line2"])
    julian_day = satellite.jdsatepoch
    fraction = satellite.jdsatepochF + case["minutes_after_epoch"] / 1440.0

    error, position, velocity = satellite.sgp4(julian_day, fraction)
    if error != 0:
        raise PropagationError(f"reference case failed with SGP4 error {error}")

    expected_position = np.array(case["expected_position_km"])
    expected_velocity = np.array(case["expected_velocity_kms"])
    position_residual = float(np.linalg.norm(np.array(position) - expected_position))
    velocity_residual = float(np.linalg.norm(np.array(velocity) - expected_velocity))

    within_tolerance = position_residual <= case["tolerance_km"]
    return {
        "case": case["name"],
        "within_tolerance": bool(within_tolerance),
        "tolerance_km": case["tolerance_km"],
        "source": case["source"],
        "minutes_after_epoch": case["minutes_after_epoch"],
        "computed_position_km": [float(v) for v in position],
        "expected_position_km": list(case["expected_position_km"]),
        "position_residual_km": position_residual,
        "position_residual_m": position_residual * 1000.0,
        "computed_velocity_kms": [float(v) for v in velocity],
        "expected_velocity_kms": list(case["expected_velocity_kms"]),
        "velocity_residual_kms": velocity_residual,
        "velocity_residual_mm_s": velocity_residual * 1e6,
    }
