import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

import research.summarize_real as sr


def test_recalibration_recovers_known_intercept_and_slope():
    rng = np.random.default_rng(1)
    q = rng.uniform(.01, .9, 20000)
    y = rng.binomial(1, expit(-.5 + 1.5 * logit(q)))
    r = sr.recalibration(y, q)
    assert r['calibration_intercept'] == pytest.approx(-.5, abs=.08) and r['calibration_slope'] == pytest.approx(1.5, abs=.08)


def test_reliability_and_frontier_are_well_formed():
    rng = np.random.default_rng(2)
    q = rng.uniform(size=500)
    y = rng.binomial(1, q)
    bins = sr.reliability(y, q, 10)
    assert len(bins) == 10 and bins.n.sum() == 500 and bins.positives.sum() == y.sum()
    f = sr.frontier(y, q)
    assert f.review_fraction.is_monotonic_decreasing and f.missed.is_monotonic_increasing
    assert f.missed.iloc[0] == 0 and f.review_fraction.iloc[0] == 1.0


def test_cluster_bootstrap_widens_with_cluster_dependence_and_needs_clusters():
    rng = np.random.default_rng(3)
    clusters = np.repeat(np.arange(15), 100)
    values = rng.normal(0, .1, 1500) + np.repeat(rng.normal(0, .2, 15), 100)
    r = sr.cluster_bootstrap_t(values, clusters, 999, 4)
    naive_half = 1.96 * values.std(ddof=1) / np.sqrt(len(values))
    assert r['lower'] < r['mean'] < r['upper'] and (r['upper'] - r['lower']) / 2 > naive_half
    with pytest.raises(ValueError):
        sr.cluster_bootstrap_t(values[:200], clusters[:200], 99, 1)


def test_paired_contrast_requires_shared_events_and_labels():
    frame = pd.DataFrame({'series_id': ['a', 'b', 'a', 'b'], 'arm': ['x', 'x', 'z', 'z'], 'y': [1, 0, 1, 0],
                          'q': [.6, .2, .5, .3], 'mission_id': [1, 2, 1, 2], 'final_risk': [-5., -30., -5., -30.]})
    d = sr.paired(frame, 'x', 'z')
    assert len(d) == 2 and d.difference.loc['a'] < 0
    bad = frame.copy()
    bad.loc[3, 'y'] = 1
    with pytest.raises(ValueError, match='label'):
        sr.paired(bad, 'x', 'z')
