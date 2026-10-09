import numpy as np
import pandas as pd
import pytest

pytest.importorskip('torch', reason='Install requirements-sequence.txt for neural comparator checks')

from research.metrics import loss
from research.summarize_sequence import paired_comparisons, reconstruct_selection


def paired_fixture():
    rows = []
    y = np.array([0, 1, 0, 1])
    for seed in (1, 2, 3):
        for arm in ('lstm_history', 'lstm_latest', 'latest_metadata'):
            for condition in ('no_reuse', 'overlap_90'):
                q = np.array([.2, .7, .1, .6])
                if arm == 'lstm_history' and condition == 'overlap_90': q = np.array([.1, .9, .1, .9])
                if arm == 'lstm_latest': q = np.array([.3, .6, .2, .5])
                rows.append(pd.DataFrame({'seed': seed, 'training_fraction': .8, 'regime': 'matched_mixture',
                    'bank': 'software', 'arm': arm, 'condition': condition, 'series_id': list('abcd'),
                    'y': y, 'q': q, 'review95': q >= .65, 'log_loss': loss(y, q)}))
    return pd.concat(rows, ignore_index=True)


def test_paired_endpoints_and_ranges_keep_actual_scenario_denominators():
    frame = paired_fixture()
    contrasts, ranges = paired_comparisons(frame)
    row = contrasts[(contrasts.seed == 1) & (contrasts.arm == 'lstm_history') &
        (contrasts.comparator == 'latest_metadata') & (contrasts.condition == 'overlap_90')].iloc[0]
    y = np.array([0, 1, 0, 1]); a = np.array([.1, .9, .1, .9]); b = np.array([.2, .7, .1, .6])
    expected = loss(y, a)-loss(y, b)
    assert row.log_loss_absolute_difference == pytest.approx(expected.mean())
    assert row.log_loss_absolute_paired_sd == pytest.approx(expected.std(ddof=1))
    assert row.log_loss_degradation_difference == pytest.approx(expected.mean())
    assert row.brier_absolute_difference == pytest.approx((np.square(a-y)-np.square(b-y)).mean())
    assert row.reviewed_absolute_difference == .25
    assert row.missed_absolute_difference == -.5
    assert row.evaluation_scenarios == 4 and row.positives == 2
    g = ranges[(ranges.arm == 'lstm_history') & (ranges.comparator == 'latest_metadata') & (ranges.condition == 'overlap_90')].iloc[0]
    assert g.neural_lower_loss_seeds == 3 and g.training_repeats == 3 and g.evaluation_scenarios == 4


def test_incomplete_pairs_and_label_disagreement_rejected():
    frame = paired_fixture()
    with pytest.raises(ValueError, match='Incomplete paired'):
        paired_comparisons(frame.drop(index=0))
    frame.loc[0, 'y'] = 1
    with pytest.raises(ValueError, match='Paired label mismatch'):
        paired_comparisons(frame)


def test_reconstruction_checks_every_candidate_and_detects_preprocessor_tampering(tmp_path):
    import json
    import torch
    from research.data import RAW_FIELDS
    from research.history import Event
    from research.sequence_campaign import fit_sequence
    from research.simulation_regimes import scenario_folds
    frame = pd.DataFrame({'series_id': [str(i) for i in range(12)], 'condition': 'no_reuse',
                          'y': np.arange(12) % 2, 'event_weight': 1.})
    events = []
    for i in range(12):
        raw = np.ones((2, len(RAW_FIELDS))); raw[:, 1] = [4., 2.]; raw[:, 0] = -9 + i*.2
        events.append(Event(str(i), raw))
    splits = scenario_folds(frame, 3, 123)
    prefix = 'seed123_no_reuse_only_lstm_history'
    _, selection = fit_sequence(frame, events, 'lstm_history', splits, [(2, 1)], 123, tmp_path, prefix)
    selection.update(seed=123, regime='no_reuse_only')
    _, records = reconstruct_selection(tmp_path, selection, frame, events, splits, [(2, 1)])
    assert len(records) == 4
    path = tmp_path/f'model_{prefix}_h2_e1_fold0.pt'
    checkpoint = torch.load(path, weights_only=True)
    checkpoint['preprocessing']['median'][0] += 1.
    torch.save(checkpoint, path)
    with pytest.raises(AssertionError):
        reconstruct_selection(tmp_path, selection, frame, events, splits, [(2, 1)])
