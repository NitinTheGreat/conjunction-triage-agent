import math

import numpy as np
import pandas as pd
import pytest

import research.precision_planning as pp
from research.metrics import loss


def predictions():
    rows = []
    q = {('h', 'no_reuse'): [.1, .8, .7, .2], ('h', 'overlap_90'): [.3, .4, .7, .2],
         ('l', 'no_reuse'): [.2, .6, .6, .1], ('l', 'overlap_90'): [.2, .6, .6, .1]}
    review = {('h', 'no_reuse'): [False, True, True, False], ('h', 'overlap_90'): [True, False, True, False],
              ('l', 'no_reuse'): [False, True, False, False], ('l', 'overlap_90'): [False, True, False, False]}
    y = [0, 1, 1, 0]
    for (arm, condition), values in q.items():
        for i, value in enumerate(values):
            rows.append({'series_id': f's{i}', 'arm': arm, 'condition': condition, 'y': y[i], 'q': value,
                         'log_loss': float(loss(np.array([y[i]]), np.array([value]))[0]), 'review95': review[arm, condition][i]})
    return pd.DataFrame(rows)


def test_contrasts_and_discordance_match_their_definitions():
    frame = predictions()
    pivots = pp.paired_frames(frame)
    lo = pivots['log_loss']
    absolute = pp.contrast(pivots, 'h', 'l', 'overlap_90', 'absolute')
    degradation = pp.contrast(pivots, 'h', 'l', 'overlap_90', 'degradation')
    np.testing.assert_allclose(absolute, lo['h', 'overlap_90'] - lo['l', 'overlap_90'])
    np.testing.assert_allclose(degradation, (lo['h', 'overlap_90'] - lo['h', 'no_reuse']) - (lo['l', 'overlap_90'] - lo['l', 'no_reuse']))
    counts = pp.discordance(pivots, 'h', 'l', 'overlap_90')
    # Positives are s1 and s2: h misses s1 (l reviews it); h reviews s2 (l misses it).
    assert counts['new_misses'] == 1 and counts['recovered_misses'] == 1 and counts['shared_misses'] == 0
    assert counts['review_arm_only'] == 2 and counts['review_comparator_only'] == 1
    # Under reuse h newly misses s1 relative to no reuse and recovers no positive.
    assert counts['reuse_new_misses_arm'] == 1 and counts['reuse_recovered_misses_arm'] == 0
    with pytest.raises(ValueError):
        pp.contrast(pivots, 'h', 'l', 'overlap_90', 'ratio')


def test_paired_frames_reject_label_mismatch_and_missing_cases():
    frame = predictions()
    bad = frame.copy()
    bad.loc[(bad.series_id == 's0') & (bad.arm == 'l') & (bad.condition == 'no_reuse'), 'y'] = 1
    with pytest.raises(ValueError, match='label'):
        pp.paired_frames(bad)
    with pytest.raises(ValueError, match='Incomplete'):
        pp.paired_frames(frame.iloc[1:])


def test_sample_size_formulas_and_exact_upper_bound():
    assert pp.n_for_half_width(.36, .01) == math.ceil((1.959963984540054 * .36 / .01) ** 2)
    expected = math.ceil(((1.959963984540054 + 1.2815515655446004) * .36 / .05) ** 2)
    assert pp.n_for_margin(.36, .07, .02) == expected
    assert math.isinf(pp.n_for_margin(.36, .02, .02))
    assert pp.clopper_pearson_upper(0, 66) == pytest.approx(1 - .05 ** (1 / 66))
    assert pp.clopper_pearson_upper(0, 299) < .01 < pp.clopper_pearson_upper(0, 298)
    assert pp.clopper_pearson_upper(5, 5) == 1.0
    with pytest.raises(ValueError):
        pp.clopper_pearson_upper(0, 0)
    assert pp.miss_bound_power(0.0, 299, .01, np.random.default_rng(1), resamples=50) == 1.0


def test_resampled_interval_covers_and_location_shift_is_exact():
    values = np.random.default_rng(3).normal(.05, .3, size=1000)
    means, ses = pp.resample_moments(values, 400, np.random.default_rng(4), resamples=2000)
    result = pp.interval_properties(means, ses, 400, float(values.mean()), 0.0)
    assert .93 <= result['coverage'] <= .97 and result['lower_above_margin'] > .9
    shifted_means, shifted_ses = pp.resample_moments(values - .05, 400, np.random.default_rng(4), resamples=2000)
    np.testing.assert_allclose(shifted_means, means - .05, atol=1e-12)
    np.testing.assert_allclose(shifted_ses, ses, atol=1e-12)
    shifted = pp.interval_properties(means - .05, ses, 400, float(values.mean()) - .05, 0.0)
    direct = pp.interval_properties(shifted_means, shifted_ses, 400, float(values.mean()) - .05, 0.0)
    assert shifted['coverage'] == pytest.approx(direct['coverage'])
    assert shifted['lower_above_margin'] == pytest.approx(direct['lower_above_margin'], abs=1e-3)


def test_reconciliation_fails_when_an_export_disagrees(tmp_path, monkeypatch):
    frame = predictions().assign(seed=1, regime=pp.REGIME, bank='software')
    pivots = pp.paired_frames(frame)
    row = {'seed': 1, 'regime': pp.REGIME, 'bank': 'software', 'arm': 'h', 'comparator': 'l', 'condition': 'overlap_90',
           'positives': 2}
    rows = pd.DataFrame([{**row, 'estimand': e, **pp.describe(pp.contrast(pivots, 'h', 'l', 'overlap_90', e)),
                          **pp.discordance(pivots, 'h', 'l', 'overlap_90')} for e in ('absolute', 'degradation')])
    exported = {**row, 'log_loss_absolute_difference': rows['mean'][0], 'log_loss_absolute_paired_sd': rows.sd[0],
                'log_loss_degradation_difference': rows['mean'][1], 'log_loss_degradation_paired_sd': rows.sd[1],
                'missed_absolute_difference': 0.0}
    (tmp_path / 'b').mkdir()
    pd.DataFrame([exported]).to_csv(tmp_path / 'b' / 'paired_contrasts.csv', index=False)
    monkeypatch.setattr(pp, 'EXPORTS', {'run': 'b'})
    checks = pp.reconcile(rows, tmp_path)
    assert checks.rows.sum() == 2 and checks.max_miss_difference.max() == 0.0
    pd.DataFrame([{**exported, 'log_loss_degradation_paired_sd': rows.sd[1] + 1e-6}]).to_csv(tmp_path / 'b' / 'paired_contrasts.csv', index=False)
    with pytest.raises(ValueError, match='disagrees'):
        pp.reconcile(rows, tmp_path)


def test_case_identity_names_the_scenario_set_independent_of_order():
    a = pp.case_identity(['s2', 's0', 's1'])
    assert a == pp.case_identity(['s0', 's1', 's2'])
    assert (a['case_ids_first'], a['case_ids_last']) == ('s0', 's2')
    assert a['case_ids_sha256'] != pp.case_identity(['s0', 's1', 's3'])['case_ids_sha256']
