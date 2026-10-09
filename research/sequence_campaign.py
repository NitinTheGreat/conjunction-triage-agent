"""Fixed-budget, whole-scenario LSTM adaptation on exposed development banks."""
from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd
import torch

from research.artifacts import ROOT, RUN_ROOT, Run, read_table, sha256, write_json, write_table
from research.covariance_campaign import check_reference
from research.history import events_from_frame
from research.metrics import class_metrics, loss
from research.models import MonotonePlatt, policy_threshold
from research.sequence_model import ARMS, SequenceModel, configure_cpu
from research.simulation_regimes import scenario_folds, training_rows
from research.summarize_pilot import audit_run
from research.tuning_stability import sample_scenarios

CONTRACT = ROOT/'docs/research/execution/sequence_contract.json'


def validate_splits(frame, events, splits):
    if len(frame) != len(events) or any(str(s) != e.identity for s, e in zip(frame.series_id, events)):
        raise ValueError('Training row/event order mismatch')
    if frame.duplicated(['series_id', 'condition']).any() or not np.isin(frame.y, [0, 1]).all():
        raise ValueError('Invalid training variants or targets')
    grouped = frame.groupby('series_id')
    if (grouped.y.nunique() != 1).any() or grouped.size().nunique() != 1:
        raise ValueError('Calibration requires consistent labels and equal variant counts')
    if not np.allclose(grouped.event_weight.sum(), 1., rtol=0, atol=1e-12):
        raise ValueError('Expected one objective unit per scenario')
    coverage = np.zeros(len(frame), dtype=int)
    for fit, valid in splits:
        if (not len(fit) or not len(valid) or len(set(fit)) != len(fit) or len(set(valid)) != len(valid)
                or set(fit) & set(valid) or set(fit) | set(valid) != set(range(len(frame)))):
            raise ValueError('Expected disjoint complete fit/validation row partitions')
        if set(frame.series_id.iloc[fit]) & set(frame.series_id.iloc[valid]):
            raise ValueError('Scenario leaks across fit/OOF boundary')
        if frame.y.iloc[fit].nunique() != 2:
            raise ValueError('Fit partition requires both classes')
        coverage[valid] += 1
    if not np.all(coverage == 1):
        raise ValueError('OOF rows must be held out exactly once')


def fit_sequence(frame, events, arm, splits, grid, seed, directory, prefix):
    validate_splits(frame, events, splits)
    start = time.perf_counter()
    y, weights = frame.y.to_numpy(), frame.event_weight.to_numpy()
    oof = {tuple(candidate): np.full(len(y), np.nan) for candidate in grid}
    records = []

    def fit_one(hidden, epochs, fit, valid, fold):
        name = f'{prefix}_h{hidden}_e{epochs}_fold{fold}'
        model_seed = seed if fold == 'refit' else seed + int(fold)
        record = {'arm': arm, 'hidden': hidden, 'epochs': epochs, 'fold': fold,
                  'initialization_seed': model_seed, 'minibatch_seed': model_seed + 1000000,
                  'fitting_scenarios': int(frame.iloc[fit].series_id.nunique()),
                  'validation_scenarios': int(frame.iloc[valid].series_id.nunique()),
                  'fitting_rows': len(fit), 'validation_rows': len(valid), 'status': 'running'}
        write_json(directory/f'fit_{name}.json', record)
        try:
            model = SequenceModel(arm, hidden, epochs, model_seed).fit([events[i] for i in fit], y[fit], weights[fit])
            model.save(directory/f'model_{name}.pt')
            prediction = model.predict(None, [events[i] for i in valid]) if len(valid) else None
            if prediction is not None:
                write_table(directory/f'validation_{name}.parquet', frame.iloc[valid].assign(row_index=valid, raw_oof=prediction))
            record.update(model.fit_record, status='complete')
            write_json(directory/f'fit_{name}.json', record)
            records.append(record)
            return model, prediction
        except Exception as exc:
            record.update(status='failed', failure_type=type(exc).__name__)
            write_json(directory/f'fit_{name}.json', record)
            raise

    for k, (fit, valid) in enumerate(splits):
        for hidden, epochs in grid:
            _, q = fit_one(hidden, epochs, fit, valid, k)
            oof[hidden, epochs][valid] = q
    if any(not np.isfinite(q).all() for q in oof.values()):
        raise ValueError('Incomplete candidate OOF predictions')
    scores = {candidate: float(np.average(loss(y, q), weights=weights)) for candidate, q in oof.items()}
    chosen = min(scores, key=lambda candidate: (scores[candidate], *candidate))
    all_oof = pd.concat([frame.assign(hidden=h, epochs=e, raw_oof=q) for (h, e), q in oof.items()], ignore_index=True)
    write_table(directory/f'candidates_{prefix}.parquet', all_oof)
    # Calibration/threshold use selected inner OOF only; no final-fit in-sample scores.
    calibration = MonotonePlatt().fit(oof[chosen], y)
    threshold = policy_threshold(calibration.predict(oof[chosen]), y, .95)
    model, _ = fit_one(*chosen, np.arange(len(frame)), np.array([], dtype=int), 'refit')
    selected = {'arm': arm, 'hidden': chosen[0], 'epochs': chosen[1],
                'inner_scores': [{'hidden': h, 'epochs': e, 'log_loss': score} for (h, e), score in scores.items()],
                'calibration_slope': calibration.slope, 'calibration_intercept': calibration.intercept,
                'threshold95': threshold, 'seconds': time.perf_counter()-start,
                'training_scenarios': int(frame.series_id.nunique()), 'training_variant_rows': len(frame),
                'objective_weight_sum': float(weights.sum()), 'completed_training_fits': len(records),
                'checkpoint': f'model_{prefix}_h{chosen[0]}_e{chosen[1]}_foldrefit.pt'}
    return {'model': model, 'calibration': calibration, 'threshold95': threshold}, selected


def evaluate_sequence(saved, banks, seed, fraction, regime, arm):
    rows = []
    for (bank, condition), (cohort, events) in banks.items():
        y = (cohort.final_risk.to_numpy() >= -6).astype(int)
        raw = saved['model'].predict(None, events)
        q = saved['calibration'].predict(raw)
        rows.append(pd.DataFrame({'series_id': cohort.series_id, 'seed': seed, 'training_fraction': fraction,
            'regime': regime, 'arm': arm, 'bank': bank, 'condition': condition, 'y': y, 'raw_q': raw,
            'q': q, 'log_loss': loss(y, q), 'threshold95': saved['threshold95'], 'review95': q >= saved['threshold95']}))
    result = pd.concat(rows, ignore_index=True)
    for _, group in result.groupby('bank'):
        p = group.pivot(index='series_id', columns='condition', values='q')
        np.testing.assert_allclose(p.no_reuse, p.exact_replay, rtol=0, atol=1e-7)
        if arm == 'lstm_latest':
            for condition in ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue'):
                np.testing.assert_allclose(p.no_reuse, p[condition], rtol=0, atol=1e-7)
    return result


def references(config):
    cadence, reference, covariance = (RUN_ROOT/config[k] for k in ('source_run', 'reference_run', 'covariance_reference_run'))
    old, compatibility = check_reference(cadence.resolve(), reference.resolve())
    compatibility['covariance_audit'] = audit_run(covariance)
    cm = json.loads((covariance/'manifest.json').read_text(encoding='utf-8'))
    assert cm['kind'] == 'covariance_proxy_development'
    assert Path(cm['config']['reference']).resolve() == reference.resolve()
    assert Path(cm['config']['source']).resolve() == cadence.resolve()
    for key in ('trials', 'regimes', 'inner_folds'):
        assert config[key] == old[key] == cm['config'][key]
    for name in ('history.py', 'covariance_proxy.py', 'models.py', 'simulation_regimes.py'):
        assert sha256(ROOT/'research'/name) == cm['code_sha256'][f'research/{name}']
    return cadence, reference, covariance, compatibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    config = json.loads(CONTRACT.read_text(encoding='utf-8'))
    committed = subprocess.check_output(['git', 'show', 'HEAD:docs/research/execution/sequence_contract.json'], cwd=ROOT)
    assert config == json.loads(committed), 'Contract must be committed before fitting'
    assert torch.__version__ == config['torch']
    configure_cpu(20261050)
    cadence, reference, covariance, compatibility = references(config)
    preflight = RUN_ROOT/config['preflight_run']
    compatibility['synthetic_preflight_audit'] = audit_run(preflight)
    grid = list(product(config['hidden_widths'], config['epochs']))
    assert config['arms'] == list(ARMS) and len(grid) == 6
    config = {**config, 'contract_commit': subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(CONTRACT)], cwd=ROOT, text=True).strip()}
    inputs = [CONTRACT, ROOT/'requirements-sequence.txt', cadence/'manifest.json', reference/'manifest.json',
              covariance/'manifest.json', preflight/'manifest.json', *sorted(cadence.glob('*.parquet')),
              *sorted(reference.glob('cohort_seed*.parquet')), *sorted(reference.glob('training_seed*.parquet'))]
    with Run(args.run_id, 'sequence_adaptation_development', config, inputs) as run:
        run.access('exposed development/software/bias banks', 'fixed-grid sequence adaptation and matched latest-only capacity control',
                   'no scientific reservation or independent cohort opened')
        write_json(run.path/'compatibility.json', compatibility)
        development = read_table(cadence/'cohort_development.parquet')
        messages = read_table(cadence/'messages_development.parquet')
        banks = {}
        for bank in ('software', 'bias_stress'):
            cohort = read_table(cadence/f'cohort_{bank}.parquet')
            assert not set(cohort.series_id) & set(development.series_id)
            for condition, group in read_table(cadence/f'messages_{bank}.parquet').groupby('condition', sort=True):
                banks[bank, condition] = cohort, events_from_frame(group, cohort.series_id.tolist())
        selections, outputs, metrics = [], [], []
        for trial in config['trials']:
            seed, fraction = trial['seed'], trial['fraction']
            cohort = read_table(reference/f'cohort_seed{seed}.parquet')
            pd.testing.assert_frame_equal(cohort, sample_scenarios(development, fraction, seed))
            for regime, conditions in config['regimes'].items():
                frame, events, _ = training_rows(cohort, messages, conditions)
                splits = scenario_folds(frame, config['inner_folds'], seed)
                membership = frame.assign(inner_fold=-1)
                for k, (_, valid) in enumerate(splits): membership.loc[valid, 'inner_fold'] = k
                pd.testing.assert_frame_equal(membership, read_table(reference/f'training_seed{seed}_{regime}.parquet'))
                write_table(run.path/f'training_seed{seed}_{regime}.parquet', membership)
                for arm in ARMS:
                    prefix = f'seed{seed}_{regime}_{arm}'
                    print('START', prefix, flush=True)
                    saved, selection = fit_sequence(frame, events, arm, splits, grid, seed, run.path, prefix)
                    selection.update(seed=seed, training_fraction=fraction, regime=regime)
                    write_json(run.path/f'selection_{prefix}.json', selection)
                    selections.append(selection)
                    output = evaluate_sequence(saved, banks, seed, fraction, regime, arm)
                    write_table(run.path/f'predictions_{prefix}.parquet', output)
                    outputs.append(output)
                    for (bank, condition), g in output.groupby(['bank', 'condition']):
                        metrics.append({'seed': seed, 'training_fraction': fraction, 'regime': regime, 'arm': arm,
                            'bank': bank, 'condition': condition, **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())})
                    write_json(run.path/'progress.json', {'completed_selected_models': len(selections),
                        'planned_selected_models': config['planned_selected_models'], 'last_completed': prefix})
                    print('DONE', prefix, 'width', selection['hidden'], 'epochs', selection['epochs'],
                          'seconds', round(selection['seconds'], 1), flush=True)
        write_json(run.path/'selections.json', selections)
        write_table(run.path/'predictions.parquet', pd.concat(outputs, ignore_index=True))
        pd.DataFrame(metrics).to_csv(run.path/'metrics.csv', index=False)
        fits = sum(s['completed_training_fits'] for s in selections)
        assert fits == config['planned_training_fits'] and len(selections) == config['planned_selected_models']
        write_json(run.path/'completion.json', {'selected_models': len(selections), 'training_fits': fits,
            'prediction_rows': sum(len(x) for x in outputs), 'scientific_bank_opened': False,
            'selected_maximum_epochs': sum(s['epochs'] == max(config['epochs']) for s in selections),
            'selected_maximum_width': sum(s['hidden'] == max(config['hidden_widths']) for s in selections)})


if __name__ == '__main__':
    main()
