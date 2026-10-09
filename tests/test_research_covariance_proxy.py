import numpy as np
import pandas as pd
import pytest

from research.covariance_proxy import PROXY_ARMS, SIGMA_FIELDS, covariance_weights
from research.data import RAW_FIELDS, visible_records
from research.history import Event, HistoryTransformer, canonicalize, events_from_frame
from research.covariance_campaign import legacy_history_matches


def prefix(volumes=(1., 4., 16.), times=(6., 4., 2.)):
    raw = np.ones((len(volumes), len(RAW_FIELDS)))
    raw[:, 0] = np.linspace(-9., -5., len(raw))
    raw[:, 1] = times
    # Four equal sigmas give (2*sigma^2)^2 = requested volume.
    raw[:, [RAW_FIELDS.index(c) for c in SIGMA_FIELDS]] = (np.asarray(volumes)/4.)[:, None]**.25
    return raw


def test_archived_control_reuse_rejects_changes_outside_new_mode_branch():
    old = 'def transform(self):\n    w = uniform\n    mean = sum(w)\n'
    new = ('from research.covariance_proxy import PROXY_ARMS, covariance_weights\n'
           'def transform(self):\n    w = uniform\n'
           '    if self.mode in PROXY_ARMS:\n        w, _ = covariance_weights(raw, self.mode)\n'
           '    mean = sum(w)\n')
    assert legacy_history_matches(new, old)
    assert not legacy_history_matches(new.replace('mean = sum(w)', 'mean = 2 * sum(w)'), old)
    assert not legacy_history_matches(new.replace('    mean =', '    else:\n        w = 0\n    mean ='), old)


@pytest.mark.parametrize('mode', PROXY_ARMS)
def test_exponential_volume_analytic_weights_and_extreme_unit_rescaling(mode):
    raw = prefix()
    expected = np.array([16., 4., 1.])/21.
    weight, reason = covariance_weights(raw, mode)
    np.testing.assert_allclose(weight, expected, rtol=1e-14)
    assert reason == 'weighted'
    for units in (1e-200, 1e200):
        scaled = raw.copy()
        scaled[:, [RAW_FIELDS.index(c) for c in SIGMA_FIELDS]] *= units
        w, _ = covariance_weights(scaled, mode)
        np.testing.assert_allclose(w, expected, rtol=1e-12)
        assert np.isfinite(w).all() and np.isclose(w.sum(), 1.)


def test_trend_is_distinct_from_direct_weighting_for_nonexponential_volume():
    raw = prefix(volumes=(1., 100., 1.))
    trend, _ = covariance_weights(raw, 'covariance_trend')
    direct, _ = covariance_weights(raw, 'covariance_direct')
    np.testing.assert_allclose(trend, np.full(3, 1/3))
    np.testing.assert_allclose(direct, np.array([1., .01, 1.])/2.01)


@pytest.mark.parametrize('invalid,reason', [(np.nan, 'invalid_sigma'), (np.inf, 'invalid_sigma'),
    (-1., 'invalid_sigma'), (0., 'nonpositive_variance')])
def test_invalid_covariance_never_becomes_precision_through_squaring_or_imputation(invalid, reason):
    raw = prefix()
    raw[1, [RAW_FIELDS.index('t_sigma_r'), RAW_FIELDS.index('c_sigma_r')]] = invalid
    for mode in PROXY_ARMS:
        w, actual = covariance_weights(raw, mode)
        np.testing.assert_array_equal(w, np.full(3, 1/3))
        assert actual == reason


def test_individual_zero_sigma_valid_but_time_and_single_message_fallbacks_explicit():
    raw = prefix()
    raw[:, RAW_FIELDS.index('t_sigma_r')] = 0
    for mode in PROXY_ARMS:
        w, reason = covariance_weights(raw, mode)
        np.testing.assert_allclose(w, np.array([16., 4., 1.])/21.)
        assert reason == 'weighted'
        for times, expected in (([2., 2., 2.], 'insufficient_times'), ([6., np.nan, 2.], 'invalid_time')):
            tied = raw.copy(); tied[:, 1] = times
            w, reason = covariance_weights(tied, mode)
            assert reason == expected
            np.testing.assert_array_equal(w, np.full(3, 1/3))
        w, reason = covariance_weights(raw[:1], mode)
        np.testing.assert_array_equal(w, [1.])
        assert reason == 'insufficient_times'


@pytest.mark.parametrize('mode', PROXY_ARMS)
def test_equal_volume_exactly_matches_singleton_design_and_objective_weight(mode):
    e = Event('uniform', canonicalize(prefix(volumes=(4., 4., 4.))))
    expected = HistoryTransformer('singleton').fit([e]).transform([e])
    actual = HistoryTransformer(mode).fit([e]).transform([e])
    for a, b in zip(actual, expected):
        np.testing.assert_array_equal(a, b)
    assert actual[2].tolist() == [1.]
    assert covariance_weights(e.raw, mode)[1] == 'constant_volume'


@pytest.mark.parametrize('mode', PROXY_ARMS)
def test_visible_prefix_replay_future_mutation_and_preprocessing_fit_boundary(mode):
    raw = prefix()
    frame = pd.DataFrame(raw, columns=RAW_FIELDS).assign(series_id='case')
    e = events_from_frame(visible_records(frame), ['case'])[0]
    t = HistoryTransformer(mode).fit([e])
    expected = t.transform([e])
    imputer, center, scale = t.imputer.statistics_.copy(), t.scaler.center_.copy(), t.scaler.scale_.copy()
    future = frame.iloc[[-1]].copy()
    future['time_to_tca'] = 1.
    future['risk'] = 1000.
    future['t_sigma_r'] = -1.
    noisy = pd.concat([frame, frame.iloc[[1]], future]).sample(frac=1., random_state=41)
    other = events_from_frame(visible_records(noisy), ['case'])
    for a, b in zip(t.transform(other), expected):
        np.testing.assert_array_equal(a, b)
    extreme = Event('test-only', canonicalize(prefix(volumes=(1e100, 1e50, 1e200))))
    t.transform([extreme])
    np.testing.assert_array_equal(t.imputer.statistics_, imputer)
    np.testing.assert_array_equal(t.scaler.center_, center)
    np.testing.assert_array_equal(t.scaler.scale_, scale)
    for a, b in zip(t.transform([e]), expected):
        np.testing.assert_array_equal(a, b)
