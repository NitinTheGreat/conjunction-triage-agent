"""Alfano (2004) two-dimensional probability of collision, implemented directly.

Reference
---------
Alfano, S. (2004). *A Numerical Implementation of Spherical Object Collision Probability*.
Journal of the Astronautical Sciences, 53(1), 103-109.

The TraCSS Users Guide documents its ``prob`` column as "Pc via Alfano 2004 method", so this
module exists to reproduce that computation. ``scripts/validate_pc.py`` compares the two.

The method
----------
Under the short-encounter approximation the objects pass so quickly that relative motion is
effectively linear and the encounter collapses to a plane perpendicular to the relative
velocity. The collision probability is then the integral of a 2D Gaussian over a disc of
radius equal to the combined hard-body radius:

.. math::

    P_c = \\frac{1}{2\\pi\\sqrt{\\det B}}
          \\iint_{x^2+y^2 \\le R^2} \\exp\\left(-\\tfrac{1}{2}
          (\\mathbf{x}-\\boldsymbol{\\mu})^T B^{-1} (\\mathbf{x}-\\boldsymbol{\\mu})\\right)
          \\,dx\\,dy

with ``B`` the combined covariance projected into the encounter plane and ``mu`` the
projected miss vector.

Alfano's contribution is an efficient evaluation: rotate to the principal axes of ``B`` so
the Gaussian separates, then integrate one axis analytically with the error function and the
other by Simpson's rule over the chord of the disc. That is what :func:`alfano_pc` does.

Covariance conditioning
-----------------------
Real covariances are not always positive-definite. Phase 2 found 65 non-PSD TraCSS
covariances (all from back-propagated historical CDMs) and Phase 4 found 38 Kelvins CDMs
with correlations at exactly -1.000000, which are singular by construction.

**The choice made here: eigenvalue flooring, reported per call, never silent.** The
projected 2x2 covariance is eigen-decomposed and any eigenvalue below a relative floor is
raised to it. This keeps the matrix invertible while changing it as little as possible, and
the amount of change is returned in a :class:`ConditioningReport` so the caller can see
whether a given Pc rested on a repaired matrix. A matrix that cannot be repaired — non-finite
entries, or a floor that would have to move an eigenvalue by more than
:data:`MAX_CONDITIONING_RATIO` — raises instead.

Rejection was the alternative. Flooring was chosen because rejecting would silently remove
exactly the diluted, badly-determined events that matter most operationally, and because the
report makes the repair visible rather than hidden.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.special import erf

from orbital.frames import (
    covariance_uvw_to_eci,
    encounter_plane_basis,
    project_covariance_to_plane,
)

__all__ = [
    "PcError",
    "ConditioningReport",
    "PcResult",
    "condition_covariance",
    "alfano_pc",
    "pc_from_states",
    "EIGENVALUE_FLOOR_RATIO",
    "MAX_CONDITIONING_RATIO",
]

#: Eigenvalues below this fraction of the largest are floored to it. 1e-12 keeps the
#: condition number under 1e12, comfortably invertible in float64 (which carries ~1e-16
#: relative precision) while barely perturbing a healthy matrix.
EIGENVALUE_FLOOR_RATIO = 1e-12

#: A matrix needing a *negative* eigenvalue raised by more than this fraction of the largest
#: is not a rounding artefact — it is not a covariance at all. Those raise.
MAX_CONDITIONING_RATIO = 1e-6

#: Simpson's rule intervals across the disc. Must be even. Alfano shows convergence well
#: before this; 200 is comfortably inside the flat part of the curve.
SIMPSON_INTERVALS = 200


class PcError(ValueError):
    """Raised when Pc cannot be computed. Never returns a default probability."""


@dataclass
class ConditioningReport:
    """What, if anything, had to be repaired before the covariance could be inverted."""

    was_conditioned: bool
    original_eigenvalues: tuple[float, ...]
    conditioned_eigenvalues: tuple[float, ...]
    smallest_original: float
    condition_number: float
    had_negative_eigenvalue: bool
    floor_applied: float

    def as_dict(self) -> dict[str, object]:
        return {
            "was_conditioned": self.was_conditioned,
            "original_eigenvalues": list(self.original_eigenvalues),
            "conditioned_eigenvalues": list(self.conditioned_eigenvalues),
            "smallest_original_eigenvalue": self.smallest_original,
            "condition_number": self.condition_number,
            "had_negative_eigenvalue": self.had_negative_eigenvalue,
            "floor_applied": self.floor_applied,
            "method": "eigenvalue flooring at EIGENVALUE_FLOOR_RATIO of the largest",
        }


@dataclass
class PcResult:
    """A probability of collision and everything needed to audit it."""

    pc: float
    miss_distance_km: float
    relative_speed_kms: float
    combined_hbr_m: float
    mahalanobis_distance: float
    mahalanobis_distance_3d: float
    projected_covariance: np.ndarray
    conditioning: ConditioningReport
    method: str = "Alfano 2004, 2D short-encounter"

    def as_dict(self) -> dict[str, object]:
        return {
            "pc": self.pc,
            "log10_pc": (
                float("-inf") if self.pc <= 0 else math.log10(self.pc)
            ),
            "miss_distance_km": self.miss_distance_km,
            "relative_speed_kms": self.relative_speed_kms,
            "combined_hbr_m": self.combined_hbr_m,
            "mahalanobis_distance": self.mahalanobis_distance,
            "mahalanobis_distance_3d": self.mahalanobis_distance_3d,
            "projected_covariance_km2": self.projected_covariance.tolist(),
            "conditioning": self.conditioning.as_dict(),
            "method": self.method,
        }


def condition_covariance(
    covariance: np.ndarray,
    floor_ratio: float = EIGENVALUE_FLOOR_RATIO,
    max_repair_ratio: float = MAX_CONDITIONING_RATIO,
) -> tuple[np.ndarray, ConditioningReport]:
    """Make a symmetric matrix safely invertible by flooring its eigenvalues.

    Returns the repaired matrix and a report of what was done. Raises if the matrix is
    non-finite, or if repairing it would require moving a negative eigenvalue by more than
    ``max_repair_ratio`` of the largest — at that point it is not a covariance and
    pretending otherwise would produce a confident, wrong number.
    """
    matrix = np.asarray(covariance, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise PcError(f"covariance must be square, got shape {matrix.shape}")
    if not np.isfinite(matrix).all():
        raise PcError("covariance contains non-finite entries")

    symmetric = 0.5 * (matrix + matrix.T)
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    largest = float(eigenvalues.max())
    if largest <= 0:
        raise PcError(
            f"covariance has no positive eigenvalue (largest {largest:.6g}); it carries "
            "no positional uncertainty and Pc is undefined"
        )

    floor = largest * floor_ratio
    smallest = float(eigenvalues.min())
    had_negative = bool(smallest < 0)

    if smallest < -max_repair_ratio * largest:
        raise PcError(
            f"covariance is not repairable: smallest eigenvalue {smallest:.6g} is "
            f"{abs(smallest) / largest:.3g} of the largest, beyond the "
            f"{max_repair_ratio:g} limit. This is not a rounding artefact."
        )

    repaired_eigenvalues = np.maximum(eigenvalues, floor)
    was_conditioned = bool(np.any(repaired_eigenvalues != eigenvalues))
    repaired = eigenvectors @ np.diag(repaired_eigenvalues) @ eigenvectors.T
    repaired = 0.5 * (repaired + repaired.T)

    report = ConditioningReport(
        was_conditioned=was_conditioned,
        original_eigenvalues=tuple(float(v) for v in eigenvalues),
        conditioned_eigenvalues=tuple(float(v) for v in repaired_eigenvalues),
        smallest_original=smallest,
        condition_number=float(repaired_eigenvalues.max() / repaired_eigenvalues.min()),
        had_negative_eigenvalue=had_negative,
        floor_applied=float(floor),
    )
    return repaired, report


def alfano_pc(
    projected_covariance: np.ndarray,
    miss_vector_km: np.ndarray,
    combined_radius_km: float,
    intervals: int = SIMPSON_INTERVALS,
) -> float:
    """Integrate a 2D Gaussian over a disc — the core of Alfano's method.

    ``projected_covariance`` is the 2x2 combined covariance in the encounter plane (km^2),
    ``miss_vector_km`` the projected miss vector (km), and ``combined_radius_km`` the sum of
    the two hard-body radii (km).

    Rotating to the principal axes of the covariance makes the Gaussian separable: the
    integral along one axis is an error function evaluated over the chord of the disc, and
    the remaining one-dimensional integral is evaluated by Simpson's rule.
    """
    covariance = np.asarray(projected_covariance, dtype=np.float64)
    miss = np.asarray(miss_vector_km, dtype=np.float64).reshape(2)
    radius = float(combined_radius_km)

    if radius < 0:
        raise PcError(f"combined radius must be non-negative, got {radius}")
    if radius == 0:
        # A zero-radius disc has zero area and therefore zero probability. Returning 0 is
        # correct rather than a fallback.
        return 0.0

    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    if eigenvalues.min() <= 0:
        raise PcError(
            f"projected covariance is not positive-definite (eigenvalues {eigenvalues}); "
            "condition it before calling alfano_pc"
        )

    # Principal-axis coordinates: the Gaussian separates and the disc stays a disc, because
    # the rotation is orthonormal.
    sigma_x, sigma_y = np.sqrt(eigenvalues)
    centre = eigenvectors.T @ miss
    x0, y0 = float(centre[0]), float(centre[1])

    if intervals % 2:
        raise PcError(f"Simpson's rule needs an even interval count, got {intervals}")

    # Integrate over x across the disc; for each x the y-extent is the chord half-width.
    #
    # The limits are the intersection of the disc with the part of the x-axis where the
    # Gaussian is non-negligible. Integrating the full [-R, R] wastes the whole grid when
    # the disc dwarfs the covariance: with R = 100 km and sigma = 1 km a fixed grid put
    # only a handful of nodes under the entire Gaussian and lost 0.5% of the mass.
    reach = 8.0 * sigma_x
    lower = max(-radius, x0 - reach)
    upper = min(radius, x0 + reach)
    if upper <= lower:
        # The Gaussian lies wholly outside the disc.
        return 0.0

    # Integrate in the angle ``t`` with ``x = R sin t`` rather than in x directly.
    #
    # The chord half-width sqrt(R^2 - x^2) meets the rim of the disc with infinite slope, and
    # Simpson's rule converges at only O(h^1.5) against that square-root singularity: at 200
    # intervals it under-reads the disc area by 1.46e-4 relative, and that bias lands
    # straight on Pc. The substitution makes the half-width R cos t and the integrand smooth,
    # restoring O(h^4). It matters here because the whole point of this module is a
    # reproduction test measured in parts per thousand.
    t_lower = math.asin(max(-1.0, min(1.0, lower / radius)))
    t_upper = math.asin(max(-1.0, min(1.0, upper / radius)))
    t = np.linspace(t_lower, t_upper, intervals + 1)
    x = radius * np.sin(t)
    half_chord = radius * np.cos(t)

    root_two = math.sqrt(2.0)
    # Analytic in y: the difference of error functions over the chord.
    y_term = 0.5 * (
        erf((y0 + half_chord) / (root_two * sigma_y))
        - erf((y0 - half_chord) / (root_two * sigma_y))
    )
    x_term = np.exp(-0.5 * ((x - x0) / sigma_x) ** 2) / (sigma_x * math.sqrt(2.0 * math.pi))
    # dx = R cos t dt, and R cos t is the half-chord itself.
    integrand = x_term * y_term * half_chord

    # Composite Simpson's rule, now in t.
    step = (t_upper - t_lower) / intervals
    weights = np.ones(intervals + 1)
    weights[1:-1:2] = 4.0
    weights[2:-1:2] = 2.0
    probability = float(step / 3.0 * np.dot(weights, integrand))

    if not np.isfinite(probability):
        raise PcError("Pc integral produced a non-finite value")
    # Clamp only against floating-point overshoot at the extremes; a value outside [0, 1]
    # by more than rounding indicates a real error and raises above.
    return float(min(max(probability, 0.0), 1.0))


def pc_from_states(
    position1_km: np.ndarray,
    velocity1_kms: np.ndarray,
    covariance1: np.ndarray,
    position2_km: np.ndarray,
    velocity2_kms: np.ndarray,
    covariance2: np.ndarray,
    hbr1_m: float,
    hbr2_m: float,
    covariance_frame: str = "uvw",
) -> PcResult:
    """Full pipeline: two states plus covariances to a probability of collision.

    ``covariance_frame`` is ``"uvw"`` (each covariance in **its own object's** local frame,
    which is how TraCSS publishes them) or ``"eci"`` (both already inertial). This argument
    exists because getting it wrong is silent: summing two covariances expressed in
    different rotated frames produces a plausible number that is simply incorrect.

    Hard-body radii are in **metres** and are converted internally; every other length is km.
    """
    r1 = np.asarray(position1_km, dtype=np.float64).reshape(3)
    v1 = np.asarray(velocity1_kms, dtype=np.float64).reshape(3)
    r2 = np.asarray(position2_km, dtype=np.float64).reshape(3)
    v2 = np.asarray(velocity2_kms, dtype=np.float64).reshape(3)

    frame = covariance_frame.lower()
    if frame == "uvw":
        c1 = covariance_uvw_to_eci(covariance1, r1, v1)
        c2 = covariance_uvw_to_eci(covariance2, r2, v2)
    elif frame == "eci":
        c1 = np.asarray(covariance1, dtype=np.float64)
        c2 = np.asarray(covariance2, dtype=np.float64)
    else:
        raise PcError(f"covariance_frame must be 'uvw' or 'eci', got {covariance_frame!r}")

    relative_position = r2 - r1
    relative_velocity = v2 - v1
    miss_distance = float(np.linalg.norm(relative_position))
    relative_speed = float(np.linalg.norm(relative_velocity))

    basis = encounter_plane_basis(relative_velocity, relative_position)
    combined_eci = c1 + c2
    projected = project_covariance_to_plane(combined_eci, basis)
    conditioned, report = condition_covariance(projected)

    miss_in_plane = basis @ relative_position
    combined_radius_km = (float(hbr1_m) + float(hbr2_m)) / 1000.0

    probability = alfano_pc(conditioned, miss_in_plane, combined_radius_km)

    # Two Mahalanobis distances, because they are different quantities and conflating them
    # is a silent error. The 2D one is the encounter-plane distance the Alfano integral
    # actually works in. The 3D one is the full-space distance, and it is what TraCSS
    # publishes as `mdistance`: scripts/validate_pc.py reproduces that column to a median
    # relative error of 6e-8, which is what pins down the covariance units (km^2) and the
    # UVW-to-ECI rotation independently of Pc.
    mahalanobis = float(
        np.sqrt(miss_in_plane @ np.linalg.solve(conditioned, miss_in_plane))
    )
    conditioned_3d, _ = condition_covariance(combined_eci)
    mahalanobis_3d = float(
        np.sqrt(relative_position @ np.linalg.solve(conditioned_3d, relative_position))
    )

    return PcResult(
        pc=probability,
        miss_distance_km=miss_distance,
        relative_speed_kms=relative_speed,
        combined_hbr_m=float(hbr1_m) + float(hbr2_m),
        mahalanobis_distance=mahalanobis,
        mahalanobis_distance_3d=mahalanobis_3d,
        projected_covariance=conditioned,
        conditioning=report,
    )
