import json

import numpy as np
import pandas as pd
import pytest

from research.metrics import loss
from research.tuning_adequacy import (FIT_NAME, load_run, logistic_profile, lstm_profile, paired_step,
    profile_groups, scenario_losses, trace_summary)

GRID = (0.01, 0.1, 1., 10., 100., 1000.)


def scores(values):
    return {str(c): v for c, v in zip(GRID, values)}


def test_logistic_profile_separates_upper_edge_interior_and_lower_edge():
    upper = logistic_profile(scores([.5, .4, .3, .25, .23, .225]), 1000.)
    assert upper['boundary'] == 'upper' and upper['setting'] == 'C=1000'
    assert upper['upper_step_gain'] == pytest.approx(.005) and upper['previous_step_gain'] == pytest.approx(.02)
    assert upper['step_ratio'] == pytest.approx(.25) and upper['adjacent_gap'] == pytest.approx(.005)
    interior = logistic_profile(scores([.5, .4, .3, .2, .21, .22]), 10.)
    assert interior['boundary'] == 'interior' and interior['upper_step_gain'] == pytest.approx(-.01)
    assert interior['adjacent_gap'] == pytest.approx(.01) and np.isnan(interior['step_ratio'])
    assert logistic_profile(scores([.1, .2, .3, .4, .5, .6]), .01)['boundary'] == 'lower'


def test_profile_rules_reproduce_campaign_ties_and_reject_wrong_selections():
    tied = scores([.5, .4, .3, .2, .2, .3])
    assert logistic_profile(tied, 10.)['adjacent_gap'] == 0.
    with pytest.raises(ValueError, match='minimum-score rule'):
        logistic_profile(tied, 100.)
    with pytest.raises(ValueError, match='finite'):
        logistic_profile(scores([.5, .4, np.nan, .2, .2, .3]), 10.)
    candidates = [{'hidden': h, 'epochs': e, 'log_loss': v} for (h, e), v in
                  {(8, 20): .3, (8, 60): .1, (16, 20): .2, (16, 60): .1, (32, 20): .15, (32, 60): .12}.items()]
    result = lstm_profile(candidates, 8, 60)
    assert result['boundary'] == 'upper_epochs;lower_width' and result['adjacent_gap'] == 0.
    assert result['upper_step_gain'] == pytest.approx(.2) and result['width_step_gain'] == pytest.approx(-.02)
    with pytest.raises(ValueError, match='minimum-score rule'):
        lstm_profile(candidates, 16, 60)
    with pytest.raises(ValueError, match='unique'):
        lstm_profile(candidates + candidates[:1], 8, 60)


def candidate_frame(q, conditions=3):
    rows = []
    for i, p in enumerate(q):
        for k in range(conditions):
            rows.append({'series_id': f's{i:02d}', 'condition': f'c{k}', 'y': i % 2,
                         'event_weight': 1/conditions, 'raw_oof': np.clip(p + .01*k, .01, .99)})
    return pd.DataFrame(rows)


def test_scenario_losses_average_to_the_weighted_campaign_score_and_reject_bad_weights():
    frame = candidate_frame(np.linspace(.2, .8, 10))
    per = scenario_losses(frame)
    expected = np.average(loss(frame.y.to_numpy(), frame.raw_oof.to_numpy()), weights=frame.event_weight)
    assert len(per) == 10 and per.mean() == pytest.approx(expected, abs=1e-14)
    with pytest.raises(ValueError, match='weight one'):
        scenario_losses(frame.assign(event_weight=.5))


def test_paired_step_uses_scenarios_as_units_and_requires_alignment():
    a = pd.Series([.3, .5, .4, .6], index=['a', 'b', 'c', 'd'])
    b = pd.Series([.2, .5, .3, .4], index=['a', 'b', 'c', 'd'])
    result = paired_step(a, b)
    gain = np.array([.1, 0., .1, .2])
    assert result['paired_gain'] == pytest.approx(gain.mean()) and result['paired_scenarios'] == 4
    assert result['paired_se'] == pytest.approx(gain.std(ddof=1)/2)
    assert result['paired_z'] == pytest.approx(gain.mean()/(gain.std(ddof=1)/2))
    with pytest.raises(ValueError, match='same scenarios'):
        paired_step(a, b.rename(index={'d': 'e'}))


def test_trace_summary_reports_late_decrease_and_minimum_epoch():
    trace = np.r_[np.linspace(1., .5, 50), np.linspace(.5, .4, 10)]
    summary = trace_summary(trace)
    assert summary['final_training_loss'] == pytest.approx(.4)
    assert summary['relative_drop_last10'] == pytest.approx((trace[-11]-.4)/trace[-11])
    assert summary['minimum_epoch'] == 60 and summary['minimum_at_final_epoch']
    plateau = trace_summary(np.r_[trace, [.41]*5])
    assert plateau['minimum_epoch'] == 60 and not plateau['minimum_at_final_epoch']
    with pytest.raises(ValueError):
        trace_summary([.5]*10)


def test_identical_complete_profiles_are_grouped_only_within_trial_and_regime():
    rows = []
    for seed in (1, 2):
        for arm, values in {'singleton': [.3, .2], 'change': [.3, .2], 'grouped': [.3, .25]}.items():
            if seed == 2 and arm == 'change':
                values = [.3, .21]
            rows += [{'seed': seed, 'regime': 'r', 'arm': arm, 'candidate': f'C={c}', 'loss': v} for c, v in zip((1, 10), values)]
    groups = profile_groups(pd.DataFrame(rows))
    assert groups[(1, 'r', 'singleton')] == groups[(1, 'r', 'change')] == 'change+singleton'
    assert groups[(2, 'r', 'singleton')] == 'singleton' and groups[(1, 'r', 'grouped')] == 'grouped'


def test_fit_record_names_supply_trial_seed_and_regime_and_must_match_contents(tmp_path):
    assert FIT_NAME.fullmatch('fit_seed20261022_matched_mixture_fixed_no_od_c0.01_fold0.json')[3] == 'fixed_no_od'
    assert FIT_NAME.fullmatch('fit_seed20261031_no_reuse_only_lstm_history_h32_e60_foldrefit.json')[4] == 'refit'
    for name, value in (('manifest.json', {}), ('selections.json', []), ('completion.json', {})):
        (tmp_path / name).write_text(json.dumps(value), encoding='utf-8')
    record = {'arm': 'grouped', 'fold': 1, 'status': 'complete'}
    (tmp_path / 'fit_seed7_no_reuse_only_grouped_c1000_fold1.json').write_text(json.dumps(record), encoding='utf-8')
    fits = load_run(tmp_path)[3]
    assert fits == [{**record, 'trial_seed': 7, 'regime': 'no_reuse_only'}]
    (tmp_path / 'fit_seed7_no_reuse_only_singleton_c1000_fold1.json').write_text(json.dumps(record), encoding='utf-8')
    with pytest.raises(ValueError, match='Unexpected fit record'):
        load_run(tmp_path)
