"""Scenario-grouped development comparison of shifted and matched training."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from research.artifacts import Run, read_table, sha256, write_json, write_table
from research.evaluate import folds
from research.history import HistoryTransformer, events_from_frame
from research.metrics import class_metrics, loss, paired_interval
from research.models import MonotonePlatt, ProbabilityModel, policy_threshold

ARMS = ('latest', 'latest_metadata', 'singleton', 'fixed', 'random', 'thin',
        'change', 'grouped', 'ignore_updates')
REGIMES = {
    'no_reuse_only': ('no_reuse',),
    'matched_mixture': ('no_reuse', 'overlap_50', 'overlap_90',
                        'solution_reissue', 'new_information', 'burst_reissue'),
}


def training_rows(cohort, messages, conditions):
    frames, events = [], []
    for condition in conditions:
        frame = cohort[['series_id', 'final_risk']].copy()
        frame['condition'] = condition
        frame['y'] = (frame.final_risk >= -6).astype(int)
        frame['event_weight'] = 1. / len(conditions)
        frames.append(frame)
        events.extend(events_from_frame(messages[messages.condition == condition], frame.series_id.tolist()))
    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(['series_id', 'condition']).any():
        raise ValueError('Repeated scenario/condition in training design')
    if combined.groupby('series_id').size().nunique() != 1:
        raise ValueError('Unequal variant counts require weighted calibration/threshold selection')
    assert np.allclose(combined.groupby('series_id').event_weight.sum(), 1.)
    X = np.array([[e.raw[-1, 0]] for e in events])
    return combined, events, X


def scenario_folds(frame, requested=3, seed=20261022):
    labels = frame.groupby('series_id', sort=False).y
    if (labels.nunique() != 1).any():
        raise ValueError('Variant label disagreement')
    scenarios = labels.first()
    result = []
    for fit, valid in folds(scenarios.to_numpy(), requested, seed):
        training_ids, validation_ids = scenarios.index[fit], scenarios.index[valid]
        a = np.flatnonzero(frame.series_id.isin(training_ids))
        b = np.flatnonzero(frame.series_id.isin(validation_ids))
        assert not set(frame.series_id.iloc[a]) & set(frame.series_id.iloc[b])
        result.append((a, b))
    return result


def fit_arm(frame, events, X, arm, splits, grid, seed, max_iter=2000, require_convergence=False):
    start = time.perf_counter()
    y, weights = frame.y.to_numpy(), frame.event_weight.to_numpy()
    oof = {c: np.full(len(y), np.nan) for c in grid}
    iterations = []

    def fit_model(c, model_seed, xx, yy, ee, ww, prepared=None):
        with warnings.catch_warnings():
            if require_convergence:
                warnings.simplefilter('error', ConvergenceWarning)
            fitted = ProbabilityModel(arm, c, model_seed, max_iter=max_iter).fit(
                xx, yy, ee, prepared=prepared, event_weights=ww)
        iterations.append(int(np.max(fitted.model[-1].n_iter_)))
        return fitted
    for k, (fit, valid) in enumerate(splits):
        ef, ev = [events[i] for i in fit], [events[i] for i in valid]
        prepared = prepared_valid = None
        if arm != 'latest':
            transform = HistoryTransformer(arm).fit(ef)
            prepared = (transform, *transform.transform(ef))
            prepared_valid = transform.transform(ev)
        for c in grid:
            model = fit_model(c, seed+k, X[fit], y[fit], ef, weights[fit], prepared)
            oof[c][valid] = model.predict(X[valid], ev, prepared=prepared_valid)
    if any(not np.isfinite(q).all() for q in oof.values()):
        raise ValueError('Incomplete OOF coverage')
    scores = {c: float(np.average(loss(y, q), weights=weights)) for c, q in oof.items()}
    chosen = min(grid, key=lambda c: (scores[c], c))
    # Every scenario has the same number of variants; uniform row means are the
    # equally weighted scenario/uniform-condition mixture for these two steps.
    calibration = MonotonePlatt().fit(oof[chosen], y)
    threshold = policy_threshold(calibration.predict(oof[chosen]), y, .95)
    model = fit_model(chosen, seed, X, y, events, weights)
    selection = {'arm': arm, 'C': chosen, 'inner_scores': {str(c): v for c, v in scores.items()},
        'calibration_slope': calibration.slope, 'calibration_intercept': calibration.intercept,
        'threshold95': threshold, 'seconds': time.perf_counter()-start,
        'training_scenarios': int(frame.series_id.nunique()), 'training_variant_rows': len(frame),
        'positive_training_scenarios': int(frame.drop_duplicates('series_id').y.sum()),
        'objective_weight_sum': float(weights.sum()), 'max_iter': max_iter,
        'maximum_observed_iterations': max(iterations), 'convergence_required': require_convergence}
    saved = {'model': model, 'calibration': calibration, 'threshold95': threshold}
    return saved, selection, oof[chosen]


def summarize(predictions):
    metrics, contrasts = {}, {}
    for (regime, arm, bank, condition), g in predictions.groupby(['regime', 'arm', 'bank', 'condition']):
        assert g.series_id.is_unique
        metrics[f'{regime}/{arm}/{bank}/{condition}'] = class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())
    for (regime, bank), g in predictions.groupby(['regime', 'bank']):
        pivot = g.pivot(index='series_id', columns=['arm', 'condition'], values='log_loss')
        q = g.pivot(index='series_id', columns=['arm', 'condition'], values='q')
        for arm in g.arm.unique():
            np.testing.assert_allclose(q[arm, 'no_reuse'], q[arm, 'exact_replay'], rtol=0, atol=1e-12)
        for arm in ('latest', 'latest_metadata'):
            for condition in ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue'):
                np.testing.assert_allclose(q[arm, 'no_reuse'], q[arm, condition], rtol=0, atol=1e-12)
        for condition in ('overlap_50', 'overlap_90', 'solution_reissue', 'new_information', 'burst_reissue'):
            for comparator in ('latest', 'latest_metadata', 'singleton', 'thin'):
                values = ((pivot['grouped', condition]-pivot['grouped', 'no_reuse'])
                          -(pivot[comparator, condition]-pivot[comparator, 'no_reuse']))
                contrasts[f'{regime}/{bank}/{condition}/grouped_minus_{comparator}'] = paired_interval(values.to_numpy())
    regime_differences = {}
    for (arm, bank, condition), g in predictions.groupby(['arm', 'bank', 'condition']):
        p = g.pivot(index='series_id', columns='regime', values='log_loss')
        regime_differences[f'{arm}/{bank}/{condition}'] = paired_interval(
            (p.matched_mixture-p.no_reuse_only).to_numpy())
    return {'models': metrics, 'degradation_contrasts': contrasts, 'matched_minus_shifted': regime_differences,
        'exact_replay_check': 'pass all arms/regimes/banks',
        'matched_latest_message_check': 'pass latest and latest_metadata',
        'evidence': 'Exposed exploratory banks; many comparisons; intervals condition on fitted models and synthetic scenarios, excluding training variability.',
        'scientific_reserved_bank_opened': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['kind'] != 'simulation_cadence_repair':
        raise ValueError('Expected completed cadence-repair run')
    inputs = [source/'manifest.json', *sorted(source.glob('*.parquet')), source/'control_diagnostics.json']
    for path in inputs[1:]:
        if sha256(path) != manifest['artifacts'][path.name]['sha256']:
            raise ValueError(f'Input mismatch: {path.name}')
    config = {'seed': 20261022, 'arms': list(ARMS), 'regimes': REGIMES, 'C': [.01, .1, 1., 10.],
        'inner_folds': 3, 'weighting': 'One objective unit per latent scenario, divided over variants and partitions',
        'preprocessing': 'Training-only unweighted message imputation/scaling; objective weighting is separate',
        'calibration_threshold_population': 'Uniform training-condition mixture; nominal 95% recall is not per-condition risk control',
        'evaluation': 'Exposed software/bias pilot banks; fixed-model descriptive intervals; no scientific bank access'}
    with Run(args.run_id, 'simulation_training_regimes', config, inputs) as run:
        run.access('existing development/software/bias banks', 'cadence/control and training-shift study',
                   'exposed exploratory scenarios; no new independent holdout')
        cohort = read_table(source/'cohort_development.parquet')
        messages = read_table(source/'messages_development.parquet')
        banks = {}
        for bank in ('software', 'bias_stress'):
            c = read_table(source/f'cohort_{bank}.parquet')
            m = read_table(source/f'messages_{bank}.parquet')
            assert not set(c.series_id) & set(cohort.series_id)
            for condition, g in m.groupby('condition', sort=True):
                events = events_from_frame(g, c.series_id.tolist())
                banks[bank, condition] = c, events, np.array([[e.raw[-1, 0]] for e in events])
        outputs, selections = [], []
        for regime, conditions in REGIMES.items():
            frame, events, X = training_rows(cohort, messages, conditions)
            splits = scenario_folds(frame, config['inner_folds'], config['seed'])
            membership = frame.copy()
            membership['inner_fold'] = -1
            for k, (_, valid) in enumerate(splits):
                membership.loc[valid, 'inner_fold'] = k
            assert (membership.inner_fold >= 0).all()
            write_table(run.path/f'training_{regime}.parquet', membership)
            for arm in ARMS:
                model, selection, oof = fit_arm(frame, events, X, arm, splits, config['C'], config['seed'])
                selection['regime'] = regime
                selections.append(selection)
                write_json(run.path/f'selection_{regime}_{arm}.json', selection)
                write_table(run.path/f'oof_{regime}_{arm}.parquet', membership.assign(raw_oof=oof))
                joblib.dump(model, run.path/f'model_{regime}_{arm}.joblib')
                arm_outputs = []
                for (bank, condition), (c, ev, xx) in banks.items():
                    y = (c.final_risk.to_numpy() >= -6).astype(int)
                    q = model['calibration'].predict(model['model'].predict(xx, ev))
                    arm_outputs.append(pd.DataFrame({'series_id': c.series_id, 'bank': bank,
                        'condition': condition, 'regime': regime, 'arm': arm, 'y': y, 'q': q,
                        'log_loss': loss(y, q), 'review95': q >= model['threshold95'],
                        'threshold95': model['threshold95']}))
                output = pd.concat(arm_outputs, ignore_index=True)
                write_table(run.path/f'predictions_{regime}_{arm}.parquet', output)
                outputs.append(output)
                print(regime, arm, 'C', selection['C'], 'fit_seconds', round(selection['seconds'], 1), flush=True)
        predictions = pd.concat(outputs, ignore_index=True)
        write_table(run.path/'predictions.parquet', predictions)
        metrics = summarize(predictions)
        metrics['selections'] = selections
        write_json(run.path/'metrics.json', metrics)
        pd.DataFrame([dict(zip(('regime', 'arm', 'bank', 'condition'), key.split('/')), **value)
                      for key, value in metrics['models'].items()]).to_csv(run.path/'metrics.csv', index=False)
        print('Completed scenario-grouped training-regime comparison.', flush=True)


if __name__ == '__main__':
    main()
