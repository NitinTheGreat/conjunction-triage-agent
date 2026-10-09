import numpy as np
import pytest
import pandas as pd

from research.simulation import posterior, PRIOR_VARIANCE
from research.state_fusion import (ELLIPSE95, check_spd, ci_weights, fuse_gaussians,
                                   oracle_estimates, state_metrics, visible_union)
from research.simulation import generate_bank
from research.simulation_v2 import repair_bank
from research.fusion_campaign import reconstruct_bank, evaluate_prepared


def test_products_separate_common_prior_from_disjoint_information():
    obs = np.arange(24, dtype=float).reshape(12, 2)/100
    estimates = [posterior(g, np.eye(2)*.09) for g in np.split(obs, 3)]
    result, _ = fuse_gaussians([e[0] for e in estimates], [e[1] for e in estimates])
    expected = posterior(obs, np.eye(2)*.09)
    for a, b in zip(result['prior_once_product'], expected):
        np.testing.assert_allclose(a, b, rtol=1e-13)
    assert np.trace(result['gaussian_product'][1]) < np.trace(expected[1])
    naive_J = np.eye(2)*(3/PRIOR_VARIANCE+12/.09)
    np.testing.assert_allclose(result['gaussian_product'][1], np.linalg.inv(naive_J))


def test_identical_covariance_tie_and_duplicate_information_failure():
    mean = np.array([.2, -.1]); P = np.eye(2)*.009
    result, info = fuse_gaussians([mean]*6, [P]*6)
    np.testing.assert_allclose(info['weights'], np.full(6, 1/6))
    np.testing.assert_allclose(result['covariance_intersection'][0], mean)
    np.testing.assert_allclose(result['covariance_intersection'][1], P)
    np.testing.assert_allclose(result['gaussian_product'][1], P/6)
    assert info['method'] == 'identical_covariance_uniform'


def test_ci_isotropic_minimum_and_anisotropic_analytic_optimum():
    w, method, gap = ci_weights([np.eye(2)*2, np.eye(2), np.eye(2)])
    np.testing.assert_array_equal(w, [0., .5, .5])
    assert gap == 0 and method == 'isotropic_minimum_equal_ties'
    P = [np.diag([1., 9.]), np.diag([9., 1.])]
    w, method, gap = ci_weights(P)
    np.testing.assert_allclose(w, [.5, .5], atol=1e-8)
    np.testing.assert_allclose(np.linalg.inv(sum(v*np.linalg.inv(p) for v, p in zip(w, P))), np.eye(2)*1.8)
    assert method == 'slsqp_uniform_start' and gap <= 1e-7


@pytest.mark.parametrize('bad', [np.diag([1., 0.]), np.diag([1., -1.]),
                                np.array([[1., 1.], [0., 1.]]), np.eye(2)*np.nan])
def test_invalid_covariance_is_rejected(bad):
    with pytest.raises(ValueError): check_spd(bad)


def test_invalid_prior_subtraction_and_failed_solver_are_not_silently_used(monkeypatch):
    with pytest.raises(ValueError, match='positive definite'):
        fuse_gaussians([[0., 0.]]*2, [np.eye(2)*100]*2)
    from types import SimpleNamespace
    monkeypatch.setattr('research.state_fusion.minimize', lambda *a, **kw:
                        SimpleNamespace(success=False, x=np.array([.5, .5])))
    with pytest.raises(RuntimeError, match='optimization failed'):
        ci_weights([np.diag([1., 9.]), np.diag([9., 1.])])


@pytest.mark.parametrize('ids', [[[0, 60]], [[-1, 2]], [[1.5]], [[True]], [[1, 1]]])
def test_invalid_or_later_observation_ids_fail(ids):
    with pytest.raises(ValueError): visible_union(ids)


def test_oracle_uses_visible_union_once_and_ignores_all_later_observations():
    obs = np.random.default_rng(42).normal(size=(80, 2))
    windows = [list(range(10)), list(range(5, 15)), list(range(10))]
    a, ids = oracle_estimates(obs, windows, True)
    np.testing.assert_array_equal(ids, np.arange(15))
    changed = obs.copy(); changed[60:] = np.nan
    b, _ = oracle_estimates(changed, windows[::-1], True)
    for name in a:
        for left, right in zip(a[name], b[name]): np.testing.assert_array_equal(left, right)
    # Independent full-joint conditional Gaussian calculation including common bias.
    H = np.tile(np.eye(2), (15, 1))
    joint = np.kron(np.eye(15), np.eye(2)*.09)+np.kron(np.ones((15, 15)), np.eye(2)*.01)
    expected_P = np.linalg.inv(np.eye(2)/PRIOR_VARIANCE+H.T @ np.linalg.solve(joint, H))
    expected_m = expected_P @ H.T @ np.linalg.solve(joint, obs[:15].ravel())
    np.testing.assert_allclose(a['oracle_bias_aware'][1], expected_P, rtol=1e-12)
    np.testing.assert_allclose(a['oracle_bias_aware'][0], expected_m, rtol=1e-12)


def test_ellipse_metrics_have_explicit_geometry_and_units():
    P = np.diag([4., 9.])
    result = state_metrics(np.array([2., 3.]), P, np.zeros(2))
    assert result['squared_error'] == 13 and result['quadratic_error'] == 2
    assert result['ellipse_contains95']
    assert result['ellipse_area95'] == pytest.approx(np.pi*ELLIPSE95*6)


def test_message_reconstruction_replay_and_later_observation_mutation():
    cohort, original, lineage, states, observations = generate_bank(2, 31, 'software')
    messages, lineage = repair_bank(original, lineage)
    reconstructed, prepared = reconstruct_bank(cohort, messages, lineage, states, observations, 'software')
    results, _ = evaluate_prepared(prepared)
    noisy = pd.concat([messages, messages.iloc[[0, 2, 10]]]).sample(frac=1., random_state=11)
    changed = observations.copy(); changed[:, 60:] = np.nan
    r2, p2 = reconstruct_bank(cohort, noisy, lineage, states, changed, 'software')
    s2, _ = evaluate_prepared(p2)
    pd.testing.assert_frame_equal(reconstructed, r2)
    pd.testing.assert_frame_equal(results, s2)
    assert reconstructed.observation_max.max() == 59
    assert len(results) == 2*7*6
    corrupted = messages.copy(); corrupted.loc[0, 'risk'] += 1
    with pytest.raises((AssertionError, ValueError)):
        reconstruct_bank(cohort, corrupted, lineage, states, observations, 'software')
