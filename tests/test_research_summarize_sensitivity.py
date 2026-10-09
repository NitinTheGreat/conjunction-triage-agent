import math

import numpy as np
import pandas as pd
import pytest

import research.summarize_sensitivity as ss
from research.metrics import loss


def test_two_way_components_recover_known_variances():
    rng = np.random.default_rng(7)
    n, k = 4000, 8
    d = (.05 + rng.normal(0, .3, size=(n, 1)) + rng.normal(0, .02, size=(1, k)) + rng.normal(0, .1, size=(n, k)))
    c = ss.two_way_components(d)
    assert c['var_scenario'] == pytest.approx(.09, rel=.08)
    assert c['var_interaction'] == pytest.approx(.01, rel=.05)
    assert c['var_bank'] == pytest.approx(.0004, rel=.9)
    assert not c['bank_truncated'] and c['grand_mean'] == pytest.approx(d.mean())
    se = ss.projected_se(c, 5, 5000)
    assert se == pytest.approx(math.sqrt(c['var_scenario'] / 5000 + c['var_bank'] / 5 + c['var_interaction'] / 25000))
    with pytest.raises(ValueError):
        ss.two_way_components(d[:, :1])


def test_negative_bank_component_is_truncated_and_flagged():
    d = np.array([[0., 1.], [1., 0.], [0., 1.], [1., 0.]])
    c = ss.two_way_components(d)
    assert c['var_bank'] == 0. and c['bank_truncated']


def predictions():
    rows = []
    for bank in ('sens_iso_t1', 'sens_iso_t2'):
        for arm in ('singleton', 'latest_metadata', 'grouped', 'oracle_lineage_weight'):
            for condition in ('no_reuse', 'overlap_90', 'solution_reissue'):
                for i in range(6):
                    y = i % 2
                    shift = .1 if (arm != 'latest_metadata' and condition != 'no_reuse') else 0.
                    q = float(np.clip(.3 + .4 * y - shift * (2 * y - 1) + .01 * (bank == 'sens_iso_t2'), .01, .99))
                    rows.append({'series_id': f's{i}', 'arm': arm, 'condition': condition, 'y': y, 'q': q,
                                 'log_loss': float(loss(np.array([y]), np.array([q]))[0]), 'review95': q >= .5,
                                 'training_configuration': 'iso', 'training_bank': bank, 'evaluation_configuration': 'iso'})
    return pd.DataFrame(rows)


def test_bank_contrasts_variance_study_and_persistence_on_a_small_layout():
    contrasts, matrices = ss.bank_contrasts(predictions())
    assert set(contrasts.id) == {c[0] for c in ss.CANDIDATES} and contrasts.training_bank.nunique() == 2
    p1 = contrasts[contrasts.id == 'P1']
    assert (p1['mean'] > 0).all()  # history degrades under overlap; latest is invariant
    components, projections = ss.variance_study(matrices, 'iso')
    assert set(components.id) == {c[0] for c in ss.CANDIDATES} and len(projections) == len(ss.CANDIDATES) * len(ss.DESIGNS)
    persist = ss.persistence(contrasts)
    assert persist.loc[persist.id == 'P1', 'banks'].iloc[0] == 2
    moved = ss.transfer(contrasts, 'iso')
    assert np.allclose(moved.transfer_mean, moved.native_mean)
