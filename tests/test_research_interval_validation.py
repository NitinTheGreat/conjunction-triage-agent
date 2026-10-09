import numpy as np
import pytest

import research.interval_validation as iv


def test_bootstrap_t_matches_t_for_symmetric_data_and_shifts_upward_for_right_skew():
    rng = np.random.default_rng(2)
    normal = rng.normal(0, 1, size=2000)
    a, b = iv.t_interval(normal)
    boot = iv.bootstrap_t_interval(normal, 1999, np.random.default_rng(3))
    assert boot['lower'] == pytest.approx(a, abs=.01) and boot['upper'] == pytest.approx(b, abs=.01)
    skewed = rng.exponential(size=400)
    a, b = iv.t_interval(skewed)
    boot = iv.bootstrap_t_interval(skewed, 1999, np.random.default_rng(3))
    assert boot['lower'] > a and boot['upper'] > b


def test_bootstrap_t_is_location_equivariant_and_rejects_constant_data():
    x = np.random.default_rng(4).exponential(size=300)
    one = iv.bootstrap_t_interval(x, 499, np.random.default_rng(5))
    two = iv.bootstrap_t_interval(x + .25, 499, np.random.default_rng(5))
    assert two['lower'] == pytest.approx(one['lower'] + .25) and two['upper'] == pytest.approx(one['upper'] + .25)
    with pytest.raises(ValueError):
        iv.bootstrap_t_interval(np.ones(50), 99, np.random.default_rng(1))


def test_validation_reports_both_one_sided_error_rates():
    values = np.random.default_rng(6).normal(.1, 1., size=1000)
    rows = iv.validate(values, 200, 300, np.random.default_rng(7), inner=199)
    assert {r['method'] for r in rows} == {'t', 'bootstrap_t', 'percentile'}
    for r in rows:
        assert 0 <= r['false_low_side'] <= .1 and 0 <= r['false_high_side'] <= .1 and r['coverage'] > .85
