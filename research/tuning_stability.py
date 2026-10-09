"""Equal-budget expanded tuning and whole-scenario training-subset sensitivity."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json, write_table
from research.history import events_from_frame
from research.metrics import class_metrics, loss
from research.simulation_regimes import ARMS, REGIMES, training_rows, scenario_folds, fit_arm

GRID = (.01, .1, 1., 10., 100., 1000.)
TRIALS = ((20261022, 1.), (20261031, .8), (20261032, .8), (20261033, .8))


def sample_scenarios(cohort, fraction, seed):
    """Stratified subset without replacement; all variants are selected later."""
    if not 0 < fraction <= 1 or not cohort.series_id.is_unique:
        raise ValueError('Expected unique scenarios and fraction in (0,1]')
    rng = np.random.default_rng(seed)
    keep = []
    for _, group in cohort.groupby(cohort.final_risk >= -6, sort=True):
        n = len(group) if fraction == 1 else int(np.floor(fraction*len(group)))
        if n < 3:
            raise ValueError('Too few scenarios per class for three inner folds')
        keep.extend(rng.choice(group.series_id.to_numpy(), size=n, replace=False))
    return cohort[cohort.series_id.isin(keep)].copy().reset_index(drop=True)


def evaluate_arm(saved, banks, seed, fraction, regime, arm):
    outputs = []
    for (bank, condition), (cohort, events, X) in banks.items():
        y = (cohort.final_risk.to_numpy() >= -6).astype(int)
        q = saved['calibration'].predict(saved['model'].predict(X, events))
        outputs.append(pd.DataFrame({'series_id': cohort.series_id, 'seed': seed,
            'training_fraction': fraction, 'regime': regime, 'arm': arm, 'bank': bank,
            'condition': condition, 'y': y, 'q': q, 'log_loss': loss(y, q),
            'threshold95': saved['threshold95'], 'review95': q >= saved['threshold95']}))
    result = pd.concat(outputs, ignore_index=True)
    for bank, group in result.groupby('bank'):
        pivot = group.pivot(index='series_id', columns='condition', values='q')
        np.testing.assert_allclose(pivot.no_reuse, pivot.exact_replay, rtol=0, atol=1e-12)
        if arm in ('latest', 'latest_metadata'):
            for condition in ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue'):
                np.testing.assert_allclose(pivot.no_reuse, pivot[condition], rtol=0, atol=1e-12)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--grid', nargs='+', type=float, default=list(GRID))
    parser.add_argument('--max-iter', type=int, default=10000)
    args = parser.parse_args()
    grid = args.grid
    if (not grid or any(not np.isfinite(c) or c <= 0 for c in grid)
            or grid != sorted(set(grid)) or args.max_iter < 1):
        raise ValueError('Grid must be positive, finite, unique and increasing; max-iter positive')
    source = args.source.resolve()
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['kind'] != 'simulation_cadence_repair':
        raise ValueError('Expected completed cadence source')
    inputs = [source/'manifest.json', *sorted(source.glob('*.parquet'))]
    for path in inputs[1:]:
        if sha256(path) != manifest['artifacts'][path.name]['sha256']:
            raise ValueError(f'Input changed: {path.name}')
    config = {'arms': list(ARMS), 'regimes': REGIMES, 'C': grid, 'inner_folds': 3,
        'trials': [{'seed': s, 'fraction': f} for s, f in TRIALS], 'max_iter': args.max_iter,
        'convergence': 'Any convergence warning fails the run; never silently drop a C/arm/trial',
        'sampling': 'Stratified scenario subsets without replacement; same subset/folds for all arms and regimes',
        'uncertainty': 'Descriptive sensitivity on overlapping subsets of one exposed development bank; not independent training-bank replication',
        'evaluation': 'Existing exposed software/bias banks; no scientific holdout access',
        'objective': 'Equal total scenario weight; no variant or seed counted as new independent evidence'}
    with Run(args.run_id, 'expanded_tuning_sensitivity', config, inputs) as run:
        run.access('exposed development/software/bias banks', 'common-grid and scenario-membership sensitivity',
                   'no new independent cohorts or reserved scenarios')
        cohort = read_table(source/'cohort_development.parquet')
        messages = read_table(source/'messages_development.parquet')
        banks = {}
        for bank in ('software', 'bias_stress'):
            c = read_table(source/f'cohort_{bank}.parquet')
            m = read_table(source/f'messages_{bank}.parquet')
            assert not set(c.series_id) & set(cohort.series_id)
            for condition, g in m.groupby('condition', sort=True):
                ev = events_from_frame(g, c.series_id.tolist())
                banks[bank, condition] = c, ev, np.array([[e.raw[-1, 0]] for e in ev])
        all_outputs, all_metrics, selections = [], [], []
        # The complete trial/grid plan is in the manifest before the first fit.
        for seed, fraction in TRIALS:
            sampled = sample_scenarios(cohort, fraction, seed)
            write_table(run.path/f'cohort_seed{seed}.parquet', sampled)
            for regime, conditions in REGIMES.items():
                frame, events, X = training_rows(sampled, messages, conditions)
                splits = scenario_folds(frame, 3, seed)
                membership = frame.copy()
                membership['inner_fold'] = -1
                for k, (_, valid) in enumerate(splits):
                    membership.loc[valid, 'inner_fold'] = k
                write_table(run.path/f'training_seed{seed}_{regime}.parquet', membership)
                for arm in ARMS:
                    prefix = f'seed{seed}_{regime}_{arm}'
                    print('START', prefix, flush=True)
                    saved, selection, oof = fit_arm(frame, events, X, arm, splits, grid, seed,
                        max_iter=args.max_iter, require_convergence=True)
                    selection.update(seed=seed, training_fraction=fraction, regime=regime)
                    selections.append(selection)
                    write_json(run.path/f'selection_{prefix}.json', selection)
                    write_table(run.path/f'oof_{prefix}.parquet', membership.assign(raw_oof=oof))
                    joblib.dump(saved, run.path/f'model_{prefix}.joblib')
                    output = evaluate_arm(saved, banks, seed, fraction, regime, arm)
                    write_table(run.path/f'predictions_{prefix}.parquet', output)
                    all_outputs.append(output)
                    for (bank, condition), g in output.groupby(['bank', 'condition']):
                        all_metrics.append({'seed': seed, 'training_fraction': fraction, 'regime': regime,
                            'arm': arm, 'bank': bank, 'condition': condition,
                            **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())})
                    write_json(run.path/'progress.json', {'completed_fits': len(selections),
                        'planned_fits': len(TRIALS)*len(REGIMES)*len(ARMS), 'last_completed': prefix})
                    print('DONE', prefix, 'C', selection['C'], 'seconds', round(selection['seconds'], 1),
                          'max_iterations', selection['maximum_observed_iterations'], flush=True)
        predictions = pd.concat(all_outputs, ignore_index=True)
        write_table(run.path/'predictions.parquet', predictions)
        pd.DataFrame(all_metrics).to_csv(run.path/'metrics.csv', index=False)
        write_json(run.path/'selections.json', selections)
        write_json(run.path/'completion.json', {'fits': len(selections), 'prediction_rows': len(predictions),
            'max_grid_selected': sum(s['C'] == max(grid) for s in selections),
            'min_grid_selected': sum(s['C'] == min(grid) for s in selections),
            'all_convergence_checks_passed': True, 'scientific_bank_opened': False,
            'replay_and_matched_latest_checks': 'pass every fit'})
        print('Completed expanded tuning and subset sensitivity.', flush=True)


if __name__ == '__main__':
    main()
