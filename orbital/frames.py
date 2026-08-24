"""Frame transforms for conjunction geometry.

Phase 3 §7 flagged frame confusion as the easiest way to be subtly wrong, so the transforms
live in one place with the convention stated explicitly and tested against hand-computable
cases.

The two frames
--------------
**ECI (J2000)** — inertial. TraCSS publishes ``x1, y1, z1`` and ``vx1, vy1, vz1`` here, in
km and km/s. Kelvins publishes only *relative* position and velocity, in the RTN frame.

**UVW / RIC / RTN** — a local orbital frame defined *per object* from its own state:

===  ==============  ====================================
Axis Name            Definition
===  ==============  ====================================
U    radial          ``r / |r|``
V    in-track        ``W × U``  (completes the right-handed set)
W    cross-track     ``(r × v) / |r × v|``
===  ==============  ====================================

Note V is **not** simply ``v / |v|``: for an eccentric orbit the velocity is not
perpendicular to the radius, so the in-track axis is constructed from the cross-product to
keep the triad orthonormal. For a circular orbit the two coincide.

TraCSS publishes each object's covariance in **that object's own UVW frame**, which means
two objects' covariances are expressed in *different* rotated frames and cannot be summed
directly. They must each be rotated to ECI first. Getting this wrong produces a plausible
number that is quietly incorrect, which is why :func:`uvw_to_eci_matrix` is separate and
tested.
"""

from __future__ import annotations

import numpy as np

__all__ = [
    "uvw_to_eci_matrix",
    "covariance_uvw_to_eci",
    "encounter_plane_basis",
    "project_covariance_to_plane",
]


class FrameError(ValueError):
    """Raised when a frame cannot be constructed. Never returns a silent fallback."""


def uvw_to_eci_matrix(position_km: np.ndarray, velocity_kms: np.ndarray) -> np.ndarray:
    """Rotation taking a vector **from** the object's UVW frame **to** ECI.

    Returns the 3x3 matrix whose columns are the UVW basis vectors expressed in ECI, so
    ``v_eci = R @ v_uvw`` and, for a covariance, ``C_eci = R @ C_uvw @ R.T``.

    Raises on a degenerate state (zero radius, or velocity parallel to radius) rather than
    returning an arbitrary triad.
    """
    r = np.asarray(position_km, dtype=np.float64).reshape(3)
    v = np.asarray(velocity_kms, dtype=np.float64).reshape(3)
    if not np.isfinite(r).all() or not np.isfinite(v).all():
        raise FrameError("position or velocity is not finite")

    r_norm = np.linalg.norm(r)
    if r_norm == 0:
        raise FrameError("position vector has zero length; UVW is undefined")
    u_hat = r / r_norm

    h = np.cross(r, v)
    h_norm = np.linalg.norm(h)
    if h_norm == 0:
        raise FrameError(
            "position and velocity are parallel (zero angular momentum); UVW is undefined"
        )
    w_hat = h / h_norm
    v_hat = np.cross(w_hat, u_hat)

    return np.column_stack((u_hat, v_hat, w_hat))


def covariance_uvw_to_eci(
    covariance_uvw: np.ndarray, position_km: np.ndarray, velocity_kms: np.ndarray
) -> np.ndarray:
    """Rotate a 3x3 position covariance from an object's UVW frame into ECI.

    ``C_eci = R C_uvw R^T``. The result is symmetrised explicitly: the rotation is exact in
    theory but floating-point error can leave a matrix marginally asymmetric, and later
    eigen-decompositions assume symmetry.
    """
    covariance = np.asarray(covariance_uvw, dtype=np.float64)
    if covariance.shape != (3, 3):
        raise FrameError(f"covariance must be 3x3, got {covariance.shape}")

    rotation = uvw_to_eci_matrix(position_km, velocity_kms)
    rotated = rotation @ covariance @ rotation.T
    return 0.5 * (rotated + rotated.T)


def encounter_plane_basis(
    relative_velocity_kms: np.ndarray, relative_position_km: np.ndarray
) -> np.ndarray:
    """Orthonormal basis of the 2D encounter plane, as a 2x3 matrix of row vectors.

    The **encounter plane** is perpendicular to the relative velocity. In the short-encounter
    approximation the objects sweep past each other so fast that motion along the relative
    velocity contributes nothing to the collision integral, so the 3D problem collapses to a
    2D one in this plane.

    The first axis is taken along the projected relative position (the miss-distance
    direction), and the second completes the right-handed pair. The choice of in-plane
    rotation does not affect the resulting probability — the integral is over a circle — but
    fixing it makes the intermediate numbers reproducible.
    """
    v_rel = np.asarray(relative_velocity_kms, dtype=np.float64).reshape(3)
    r_rel = np.asarray(relative_position_km, dtype=np.float64).reshape(3)

    v_norm = np.linalg.norm(v_rel)
    if v_norm == 0:
        raise FrameError(
            "relative velocity is zero; the encounter plane and the short-encounter "
            "approximation are both undefined"
        )
    v_hat = v_rel / v_norm

    # Component of the relative position perpendicular to the relative velocity.
    in_plane = r_rel - np.dot(r_rel, v_hat) * v_hat
    in_plane_norm = np.linalg.norm(in_plane)
    if in_plane_norm < 1e-12:
        # A head-on encounter with no perpendicular offset: any in-plane basis is valid,
        # so pick one deterministically rather than dividing by ~0.
        arbitrary = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(arbitrary, v_hat)) > 0.9:
            arbitrary = np.array([0.0, 1.0, 0.0])
        x_hat = arbitrary - np.dot(arbitrary, v_hat) * v_hat
        x_hat /= np.linalg.norm(x_hat)
    else:
        x_hat = in_plane / in_plane_norm

    y_hat = np.cross(v_hat, x_hat)
    return np.vstack((x_hat, y_hat))


def project_covariance_to_plane(
    covariance_eci: np.ndarray, basis: np.ndarray
) -> np.ndarray:
    """Project a 3x3 ECI covariance into the 2D encounter plane: ``B = P C P^T``."""
    covariance = np.asarray(covariance_eci, dtype=np.float64)
    projection = np.asarray(basis, dtype=np.float64)
    if covariance.shape != (3, 3):
        raise FrameError(f"covariance must be 3x3, got {covariance.shape}")
    if projection.shape != (2, 3):
        raise FrameError(f"basis must be 2x3, got {projection.shape}")

    projected = projection @ covariance @ projection.T
    return 0.5 * (projected + projected.T)
