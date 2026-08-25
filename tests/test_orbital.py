"""Tests for the Phase 9 physics layer: frames, Pc, and SGP4 propagation.

Every case here is either analytic (a limit with a closed form), independent (the same
quantity computed a different way), or published (the Vallado SGP4 verification case). None
of them compares the module against itself.

Offline by construction: no TLE is fetched, no dataset file is read.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from orbital.frames import (
    FrameError,
    covariance_uvw_to_eci,
    encounter_plane_basis,
    project_covariance_to_plane,
    uvw_to_eci_matrix,
)
from orbital.pc import PcError, alfano_pc, condition_covariance, pc_from_states
from orbital.propagate import (
    REFERENCE_CASE,
    PropagationError,
    propagate_series,
    propagate_tle,
    screen_pair,
    verify_reference_case,
)

# A circular equatorial state: r along +x, v along +y.
CIRCULAR_POSITION = np.array([7000.0, 0.0, 0.0])
CIRCULAR_VELOCITY = np.array([0.0, 7.5, 0.0])


# -- frames ------------------------------------------------------------------------------


def test_uvw_matrix_is_a_proper_rotation():
    rotation = uvw_to_eci_matrix(CIRCULAR_POSITION, CIRCULAR_VELOCITY)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
    assert pytest.approx(1.0, abs=1e-12) == float(np.linalg.det(rotation))


def test_uvw_axes_for_a_hand_computable_circular_state():
    """For r along +x and v along +y: U=+x, W=+z, V=+y."""
    rotation = uvw_to_eci_matrix(CIRCULAR_POSITION, CIRCULAR_VELOCITY)
    np.testing.assert_allclose(rotation[:, 0], [1, 0, 0], atol=1e-12)
    np.testing.assert_allclose(rotation[:, 1], [0, 1, 0], atol=1e-12)
    np.testing.assert_allclose(rotation[:, 2], [0, 0, 1], atol=1e-12)


def test_in_track_axis_is_not_the_velocity_direction_when_eccentric():
    """The distinction the module documents: V comes from W x U, not from v/|v|."""
    velocity = np.array([1.0, 7.5, 0.0])  # radial component present
    rotation = uvw_to_eci_matrix(CIRCULAR_POSITION, velocity)
    v_hat = velocity / np.linalg.norm(velocity)
    assert not np.allclose(rotation[:, 1], v_hat, atol=1e-6)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)


def test_degenerate_states_raise_rather_than_guess():
    with pytest.raises(FrameError):
        uvw_to_eci_matrix([0.0, 0.0, 0.0], CIRCULAR_VELOCITY)
    with pytest.raises(FrameError):
        uvw_to_eci_matrix(CIRCULAR_POSITION, CIRCULAR_POSITION * 0.001)  # v parallel to r


def test_covariance_rotation_preserves_trace_and_eigenvalues():
    """A similarity transform by a rotation changes the axes, not the spectrum."""
    covariance = np.diag([0.01, 4.0, 0.09])
    rotated = covariance_uvw_to_eci(covariance, [3000.0, 4000.0, 5000.0], [-5.0, 2.0, 3.0])
    assert pytest.approx(float(np.trace(covariance)), rel=1e-12) == float(np.trace(rotated))
    np.testing.assert_allclose(
        np.sort(np.linalg.eigvalsh(rotated)), np.sort(np.diag(covariance)), atol=1e-10
    )
    np.testing.assert_allclose(rotated, rotated.T, atol=1e-15)


def test_encounter_plane_basis_is_orthonormal_and_kills_the_relative_velocity():
    v_rel = np.array([1.0, -14.0, 2.0])
    r_rel = np.array([0.4, 0.1, -3.0])
    basis = encounter_plane_basis(v_rel, r_rel)
    assert basis.shape == (2, 3)
    np.testing.assert_allclose(basis @ basis.T, np.eye(2), atol=1e-12)
    np.testing.assert_allclose(basis @ v_rel, [0.0, 0.0], atol=1e-12)


def test_projected_miss_equals_the_perpendicular_miss_distance():
    """The first basis axis is the miss direction, so the projection has one component."""
    v_rel = np.array([0.0, -14.0, 0.0])
    r_rel = np.array([3.0, 5.0, 4.0])
    basis = encounter_plane_basis(v_rel, r_rel)
    projected = basis @ r_rel
    assert pytest.approx(5.0, abs=1e-12) == float(np.linalg.norm(projected))  # sqrt(9+16)
    assert pytest.approx(0.0, abs=1e-12) == float(projected[1])


def test_head_on_encounter_with_no_offset_still_yields_a_basis():
    basis = encounter_plane_basis([0.0, 0.0, -10.0], [0.0, 0.0, 500.0])
    np.testing.assert_allclose(basis @ basis.T, np.eye(2), atol=1e-12)


def test_projection_rejects_wrong_shapes():
    with pytest.raises(FrameError):
        project_covariance_to_plane(np.eye(2), np.zeros((2, 3)))
    with pytest.raises(FrameError):
        project_covariance_to_plane(np.eye(3), np.zeros((3, 3)))


# -- Pc: analytic limits -------------------------------------------------------------------


def test_tiny_disc_matches_the_analytic_density_times_area():
    """When R << sigma the Gaussian is flat across the disc, so Pc -> f(mu) * pi R^2."""
    covariance = np.diag([1.0, 4.0])  # km^2
    miss = np.array([0.5, -1.0])
    radius = 1e-4  # km, ~10 cm: four orders below the smallest sigma

    density = (
        1.0
        / (2 * math.pi * math.sqrt(float(np.linalg.det(covariance))))
        * math.exp(-0.5 * float(miss @ np.linalg.inv(covariance) @ miss))
    )
    expected = density * math.pi * radius**2
    assert pytest.approx(expected, rel=1e-6) == alfano_pc(covariance, miss, radius)


def test_disc_swallowing_the_whole_distribution_gives_probability_one():
    """R >> sigma: the disc contains essentially all the mass."""
    assert pytest.approx(1.0, abs=1e-9) == alfano_pc(np.diag([1.0, 1.0]), [0.0, 0.0], 100.0)


def test_quadrature_does_not_lose_mass_at_the_rim_of_the_disc():
    """Guards the trigonometric substitution in :func:`alfano_pc`.

    Integrating directly in x, Simpson's rule meets the square-root singularity of the chord
    half-width at the rim and under-reads the disc by 1.46e-4 relative at 200 intervals --
    a bias that lands straight on Pc and was visible in the reproduction gate. Held here
    because it is far too small to notice by eye.
    """
    covariance = np.diag([1.0, 1.0])
    miss = np.array([0.0, 0.0])
    radius = 1e-3
    exact = (1.0 - math.exp(-0.5 * radius**2))  # closed form for an isotropic centred disc
    assert pytest.approx(exact, rel=1e-8) == alfano_pc(covariance, miss, radius)


def test_matches_independent_two_dimensional_quadrature():
    """Cross-check against a brute-force grid integral of the same integrand."""
    covariance = np.array([[2.0, 0.8], [0.8, 0.5]])
    miss = np.array([0.6, -0.3])
    radius = 0.9

    inverse = np.linalg.inv(covariance)
    normalisation = 1.0 / (2 * math.pi * math.sqrt(float(np.linalg.det(covariance))))
    axis = np.linspace(-radius, radius, 1601)
    grid_x, grid_y = np.meshgrid(axis, axis, indexing="ij")
    inside = grid_x**2 + grid_y**2 <= radius**2
    dx = grid_x - miss[0]
    dy = grid_y - miss[1]
    quadratic = (
        inverse[0, 0] * dx**2 + 2 * inverse[0, 1] * dx * dy + inverse[1, 1] * dy**2
    )
    cell = (axis[1] - axis[0]) ** 2
    reference = float(normalisation * np.sum(np.exp(-0.5 * quadratic) * inside) * cell)

    assert pytest.approx(reference, rel=2e-4) == alfano_pc(covariance, miss, radius)


def test_zero_radius_gives_exactly_zero():
    assert alfano_pc(np.eye(2), [0.0, 0.0], 0.0) == 0.0


def test_pc_falls_as_the_miss_distance_grows():
    covariance = np.diag([1.0, 1.0])
    values = [alfano_pc(covariance, [d, 0.0], 0.01) for d in (0.0, 1.0, 2.0, 5.0)]
    assert values == sorted(values, reverse=True)


def test_non_positive_definite_projected_covariance_raises():
    with pytest.raises(PcError):
        alfano_pc(np.diag([1.0, -1.0]), [0.0, 0.0], 0.01)


def test_odd_interval_count_raises():
    with pytest.raises(PcError):
        alfano_pc(np.eye(2), [0.0, 0.0], 0.01, intervals=201)


# -- Pc: conditioning ----------------------------------------------------------------------


def test_singular_covariance_is_repaired_and_the_repair_is_reported():
    singular = np.array([[1.0, 1.0], [1.0, 1.0]])  # one zero eigenvalue
    repaired, report = condition_covariance(singular)
    assert report.was_conditioned is True
    assert report.smallest_original == pytest.approx(0.0, abs=1e-15)
    assert float(np.linalg.eigvalsh(repaired).min()) > 0
    assert "flooring" in report.as_dict()["method"]


def test_healthy_covariance_is_left_alone():
    healthy = np.diag([1.0, 2.0])
    repaired, report = condition_covariance(healthy)
    assert report.was_conditioned is False
    np.testing.assert_allclose(repaired, healthy, atol=1e-15)


def test_grossly_negative_eigenvalue_is_rejected_not_repaired():
    with pytest.raises(PcError, match="not repairable"):
        condition_covariance(np.diag([1.0, -0.5]))


def test_tiny_negative_eigenvalue_is_treated_as_a_rounding_artefact():
    _, report = condition_covariance(np.diag([1.0, -1e-14]))
    assert report.had_negative_eigenvalue is True
    assert report.was_conditioned is True


def test_non_finite_covariance_raises():
    with pytest.raises(PcError):
        condition_covariance(np.array([[1.0, np.nan], [np.nan, 1.0]]))


# -- Pc: end to end ------------------------------------------------------------------------


def _offset_pair(offset_km):
    """Two objects crossing at right angles, separated by ``offset_km`` along +z."""
    r1 = np.array([7000.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.5, 0.0])
    r2 = r1 + np.array([0.0, 0.0, offset_km])
    v2 = np.array([0.0, 0.0, 7.5])
    return r1, v1, r2, v2


def test_pc_from_states_reproduces_the_geometry_it_was_given():
    r1, v1, r2, v2 = _offset_pair(0.5)
    result = pc_from_states(
        r1, v1, np.diag([1e-4, 1e-2, 1e-4]),
        r2, v2, np.diag([1e-4, 1e-2, 1e-4]),
        hbr1_m=5.0, hbr2_m=5.0,
    )
    assert pytest.approx(0.5, abs=1e-12) == result.miss_distance_km
    assert pytest.approx(math.hypot(7.5, 7.5), rel=1e-12) == result.relative_speed_kms
    assert result.combined_hbr_m == 10.0
    assert 0.0 <= result.pc <= 1.0


def test_both_mahalanobis_distances_are_computed_and_differ():
    """The 2D and 3D distances are different quantities and must not be conflated.

    The 3D one is what TraCSS publishes as ``mdistance``; the 2D one is the encounter-plane
    distance the Alfano integral works in. Here the covariance is isotropic in ECI, so the
    3D value has a closed form: |dr| / sigma.
    """
    r1, v1, r2, v2 = _offset_pair(0.5)
    isotropic = np.eye(3) * 0.04  # sigma = 0.2 km on every axis, so rotation is irrelevant
    result = pc_from_states(r1, v1, isotropic, r2, v2, isotropic,
                            hbr1_m=5.0, hbr2_m=5.0)

    combined_sigma = math.sqrt(0.04 + 0.04)
    assert pytest.approx(0.5 / combined_sigma, rel=1e-12) == result.mahalanobis_distance_3d
    # Projecting into the plane discards the along-velocity component, so the plane distance
    # can only be smaller or equal.
    assert result.mahalanobis_distance <= result.mahalanobis_distance_3d + 1e-12


def test_uvw_and_eci_paths_differ_by_orders_of_magnitude():
    """Summing covariances expressed in two different local frames is silently wrong.

    The two readings of the same numbers differ by seven orders of magnitude here, which is
    the size of the mistake ``covariance_frame`` exists to prevent: an in-track-dominated
    covariance rotated into ECI covers the miss vector, and left unrotated it does not.
    """
    r1 = np.array([7000.0, 0.0, 0.0])
    v1 = np.array([0.0, 7.5, 0.0])
    r2 = r1 + np.array([0.2, 0.1, 0.3])
    v2 = np.array([2.0, 3.0, 6.5])  # a genuinely different orbital plane
    anisotropic = np.diag([1e-4, 4.0, 1e-4])  # dominated by the in-track axis

    as_uvw = pc_from_states(r1, v1, anisotropic, r2, v2, anisotropic,
                            hbr1_m=10.0, hbr2_m=10.0, covariance_frame="uvw")
    as_eci = pc_from_states(r1, v1, anisotropic, r2, v2, anisotropic,
                            hbr1_m=10.0, hbr2_m=10.0, covariance_frame="eci")
    assert as_uvw.pc / as_eci.pc > 1e6


def test_unknown_frame_raises():
    r1, v1, r2, v2 = _offset_pair(0.3)
    with pytest.raises(PcError):
        pc_from_states(r1, v1, np.eye(3), r2, v2, np.eye(3),
                       hbr1_m=1.0, hbr2_m=1.0, covariance_frame="rtn")


# -- propagation ---------------------------------------------------------------------------


def test_sgp4_reference_case_reproduces_the_published_state():
    """The Vallado verification case, read from the sgp4 package's own tcppver.out."""
    report = verify_reference_case()
    assert report["within_tolerance"] is True
    assert report["position_residual_km"] < 1e-3
    assert report["velocity_residual_kms"] < 1e-6


def test_propagate_tle_requires_an_aware_datetime():
    with pytest.raises(PropagationError):
        propagate_tle(REFERENCE_CASE["line1"], REFERENCE_CASE["line2"],
                      datetime(1980, 10, 2))


def test_propagate_series_matches_pointwise_propagation():
    start = datetime(1980, 10, 1, 23, 41, 24, tzinfo=timezone.utc)
    series = propagate_series(REFERENCE_CASE["line1"], REFERENCE_CASE["line2"],
                              start, start + timedelta(minutes=10), 120.0)
    assert len(series) == 6
    single = propagate_tle(REFERENCE_CASE["line1"], REFERENCE_CASE["line2"],
                           series[3].epoch_utc)
    np.testing.assert_allclose(single.position, series[3].position, atol=1e-9)
    assert series[0].frame == "TEME"


def test_propagate_series_rejects_a_backwards_window():
    start = datetime(1980, 10, 1, tzinfo=timezone.utc)
    with pytest.raises(PropagationError):
        propagate_series(REFERENCE_CASE["line1"], REFERENCE_CASE["line2"],
                         start, start, 60.0)


def test_malformed_tle_raises_rather_than_returning_a_state():
    with pytest.raises(PropagationError):
        propagate_tle("not a tle", "nor is this",
                      datetime(2026, 1, 1, tzinfo=timezone.utc))


def test_screen_pair_finds_the_self_conjunction_of_an_object_with_itself():
    """An object screened against itself has zero range at every step, so the screen must
    report an approach rather than silently finding nothing."""
    tle = (REFERENCE_CASE["line1"], REFERENCE_CASE["line2"])
    start = datetime(1980, 10, 1, 23, 41, 24, tzinfo=timezone.utc)
    approaches = screen_pair(tle, tle, start, start + timedelta(minutes=20),
                             threshold_km=1.0, coarse_step_seconds=60.0,
                             refine_step_seconds=5.0)
    assert approaches, "screening an object against itself found no approach"
    assert approaches[0].miss_distance_km == pytest.approx(0.0, abs=1e-9)
