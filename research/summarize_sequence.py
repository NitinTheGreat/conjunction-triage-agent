"""Reconstruct every neural fit/OOF/forecast and compare saved paired controls."""
from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json
from research.metrics import class_metrics, loss
from research.models import MonotonePlatt, policy_threshold
from research.sequence_campaign import evaluate_sequence, references, validate_splits
from research.sequence_model import ARMS, SequenceModel, SequenceTransform, configure_cpu
from research.history import events_from_frame
from research.simulation_regimes import scenario_folds, training_rows
from research.summarize_pilot import audit_run, table
from research.summarize_tuning import stability_tables


def paired_comparisons(predictions):
    """Scenario-paired differences; no pseudo-replication over training trials."""
    rows = []
    for key, g in predictions.groupby(['seed', 'training_fraction', 'regime', 'bank']):
        y = g.groupby('series_id').y
        if (y.nunique() != 1).any():
            raise ValueError('Paired label mismatch')
        y = y.first()
        g = g.assign(brier=np.square(g.q-g.y), reviewed=g.review95.astype(float),
                     missed=(g.y.eq(1) & ~g.review95.astype(bool)).astype(float))
        pivots = {metric: g.pivot(index='series_id', columns=['arm', 'condition'], values=metric)
                  for metric in ('log_loss', 'brier', 'reviewed', 'missed')}
        if any(p.isna().any().any() for p in pivots.values()):
            raise ValueError('Incomplete paired scenario coverage')
        for arm in ARMS:
            for comparator in sorted(set(g.arm)-{arm}):
                for condition in sorted(g.condition.unique()):
                    row = dict(zip(['seed', 'training_fraction', 'regime', 'bank'], key), arm=arm,
                        comparator=comparator, condition=condition, evaluation_scenarios=len(y), positives=int(y.sum()))
                    for metric, p in pivots.items():
                        absolute = p[arm, condition]-p[comparator, condition]
                        degradation = absolute-(p[arm, 'no_reuse']-p[comparator, 'no_reuse'])
                        if metric == 'missed':
                            absolute, degradation = absolute[y.eq(1)], degradation[y.eq(1)]
                        row.update({f'{metric}_absolute_difference': float(absolute.mean()),
                                    f'{metric}_absolute_paired_sd': float(absolute.std(ddof=1)),
                                    f'{metric}_degradation_difference': float(degradation.mean()),
                                    f'{metric}_degradation_paired_sd': float(degradation.std(ddof=1))})
                    rows.append(row)
    contrasts = pd.DataFrame(rows)
    ranges = []
    keys = ['regime', 'bank', 'arm', 'comparator', 'condition']
    for key, group in contrasts[contrasts.training_fraction < 1].groupby(keys):
        if not group.seed.is_unique or group.evaluation_scenarios.nunique() != 1:
            raise ValueError('Invalid repeated evaluation units')
        row = dict(zip(keys, key), training_repeats=len(group), evaluation_scenarios=int(group.evaluation_scenarios.iloc[0]),
                   neural_lower_loss_seeds=int((group.log_loss_absolute_difference < -1e-12).sum()))
        for metric in ('log_loss', 'brier', 'reviewed', 'missed'):
            for contrast in ('absolute', 'degradation'):
                name = f'{metric}_{contrast}_difference'
                for stat in ('mean', 'min', 'max'):
                    row[f'{name}_{stat}'] = float(getattr(group[name], stat)())
        ranges.append(row)
    return contrasts, pd.DataFrame(ranges)


def reconstruct_selection(source, selection, frame, events, splits, grid):
    seed, regime, arm = (selection[k] for k in ('seed', 'regime', 'arm'))
    prefix = f'seed{seed}_{regime}_{arm}'
    validate_splits(frame, events, splits)
    assert selection['training_scenarios'] == frame.series_id.nunique()
    assert selection['training_variant_rows'] == len(frame)
    assert selection['objective_weight_sum'] == float(frame.event_weight.sum())
    candidates = read_table(source/f'candidates_{prefix}.parquet')
    scores, records = [], []
    # Refit preprocessing only, using the audited fitting rows, never labels.
    transforms = [SequenceTransform().fit([events[i] for i in fit]).state() for fit, _ in splits]
    for hidden, epochs in grid:
        rows = candidates[(candidates.hidden == hidden) & (candidates.epochs == epochs)].reset_index(drop=True)
        pd.testing.assert_frame_equal(rows.drop(columns=['hidden', 'epochs', 'raw_oof']), frame)
        reconstructed = np.full(len(frame), np.nan)
        for k, (fit, valid) in enumerate(splits):
            name = f'{prefix}_h{hidden}_e{epochs}_fold{k}'
            model = SequenceModel.load(source/f'model_{name}.pt')
            record = json.loads((source/f'fit_{name}.json').read_text(encoding='utf-8'))
            assert record['status'] == 'complete' and model.arm == arm
            assert model.seed == record['initialization_seed'] == seed+k
            assert record['minibatch_seed'] == seed+k+1000000
            assert model.hidden == hidden and model.epochs == epochs
            assert len(record['epoch_training_loss']) == epochs and np.isfinite(record['epoch_training_loss']).all()
            assert record['fitting_rows'] == len(fit) and record['validation_rows'] == len(valid)
            assert record['fitting_scenarios'] == frame.iloc[fit].series_id.nunique()
            assert record['validation_scenarios'] == frame.iloc[valid].series_id.nunique()
            assert model.transformer.state() == transforms[k]
            assert model.fit_record == {key: record[key] for key in model.fit_record}
            q = model.predict(None, [events[i] for i in valid])
            recorded = read_table(source/f'validation_{name}.parquet')
            pd.testing.assert_frame_equal(recorded.drop(columns=['row_index', 'raw_oof']), frame.iloc[valid].reset_index(drop=True))
            np.testing.assert_array_equal(recorded.row_index, valid)
            np.testing.assert_array_equal(q, recorded.raw_oof)
            reconstructed[valid] = q
            records.append({**{k: selection[k] for k in ('seed', 'regime', 'arm')}, **record})
        np.testing.assert_array_equal(reconstructed, rows.raw_oof)
        score = float(np.average(loss(frame.y.to_numpy(), reconstructed), weights=frame.event_weight))
        scores.append({'hidden': hidden, 'epochs': epochs, 'log_loss': score})
    assert len(candidates) == len(frame)*len(grid)
    assert selection['inner_scores'] == scores
    chosen = min(scores, key=lambda s: (s['log_loss'], s['hidden'], s['epochs']))
    assert (selection['hidden'], selection['epochs']) == (chosen['hidden'], chosen['epochs'])
    oof = candidates[(candidates.hidden == chosen['hidden']) & (candidates.epochs == chosen['epochs'])].raw_oof.to_numpy()
    calibration = MonotonePlatt().fit(oof, frame.y.to_numpy())
    assert calibration.slope == selection['calibration_slope'] and calibration.intercept == selection['calibration_intercept']
    assert policy_threshold(calibration.predict(oof), frame.y.to_numpy(), .95) == selection['threshold95']
    model = SequenceModel.load(source/selection['checkpoint'])
    assert model.arm == arm and model.seed == seed
    assert model.hidden == chosen['hidden'] and model.epochs == chosen['epochs']
    assert model.transformer.state() == SequenceTransform().fit(events).state()
    refit = json.loads((source/selection['checkpoint'].replace('model_', 'fit_', 1).replace('.pt', '.json')).read_text(encoding='utf-8'))
    assert refit['status'] == 'complete' and refit['fitting_rows'] == len(frame) and refit['validation_rows'] == 0
    assert refit['fitting_scenarios'] == frame.series_id.nunique() and refit['validation_scenarios'] == 0
    assert refit['initialization_seed'] == seed and refit['minibatch_seed'] == seed+1000000
    assert (refit['hidden'], refit['epochs'], refit['arm']) == (model.hidden, model.epochs, arm)
    assert model.fit_record == {key: refit[key] for key in model.fit_record}
    assert len(refit['epoch_training_loss']) == chosen['epochs']
    assert selection['completed_training_fits'] == len(records)+1
    records.append({**{k: selection[k] for k in ('seed', 'regime', 'arm')}, **refit})
    return {'model': model, 'calibration': calibration, 'threshold95': selection['threshold95']}, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args()
    if args.export.exists(): raise FileExistsError(args.export)
    source = args.source.resolve()
    source_audit = audit_run(source)
    manifest = json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['kind'] == 'sequence_adaptation_development'
    config = manifest['config']
    cadence, reference, covariance, compatibility = references(config)
    for name in ('sequence_model.py', 'sequence_campaign.py', 'history.py', 'data.py', 'models.py', 'metrics.py'):
        assert sha256(ROOT/'research'/name) == manifest['code_sha256'][f'research/{name}']
    configure_cpu(20261050)
    with Run(args.run_id, 'sequence_adaptation_reconstruction', {'source': str(source)},
             [source/'manifest.json', reference/'manifest.json', covariance/'manifest.json']) as run:
        new = read_table(source/'predictions.parquet')
        combined = pd.concat([read_table(reference/'predictions.parquet'), read_table(covariance/'predictions.parquet'), new], ignore_index=True)
        selections = json.loads((source/'selections.json').read_text(encoding='utf-8'))
        grid = list(product(config['hidden_widths'], config['epochs']))
        banks = {}
        for bank in ('software', 'bias_stress'):
            cohort = read_table(cadence/f'cohort_{bank}.parquet')
            for condition, group in read_table(cadence/f'messages_{bank}.parquet').groupby('condition', sort=True):
                banks[bank, condition] = cohort, events_from_frame(group, cohort.series_id.tolist())
        messages = read_table(cadence/'messages_development.parquet')
        fit_records, profiles = [], []
        assert len(selections) == config['planned_selected_models']
        expected_models = set(product([t['seed'] for t in config['trials']], config['regimes'], ARMS))
        assert {(s['seed'], s['regime'], s['arm']) for s in selections} == expected_models
        for selection in selections:
            seed, regime, arm = (selection[k] for k in ('seed', 'regime', 'arm'))
            cohort = read_table(reference/f'cohort_seed{seed}.parquet')
            frame, events, _ = training_rows(cohort, messages, config['regimes'][regime])
            splits = scenario_folds(frame, config['inner_folds'], seed)
            membership = frame.assign(inner_fold=-1)
            for k, (_, valid) in enumerate(splits): membership.loc[valid, 'inner_fold'] = k
            for directory in (reference, source):
                pd.testing.assert_frame_equal(membership, read_table(directory/f'training_seed{seed}_{regime}.parquet'))
            saved, records = reconstruct_selection(source, selection, frame, events, splits, grid)
            fit_records.extend(records)
            output = evaluate_sequence(saved, banks, seed, selection['training_fraction'], regime, arm)
            recorded = new[(new.seed == seed) & (new.regime == regime) & (new.arm == arm)].reset_index(drop=True)
            pd.testing.assert_frame_equal(output, recorded, check_exact=True)
            profiles.extend({'seed': seed, 'regime': regime, 'arm': arm, **p,
                'selected': p['hidden'] == selection['hidden'] and p['epochs'] == selection['epochs']} for p in selection['inner_scores'])
            print('RECONSTRUCTED', seed, regime, arm, flush=True)
        assert len(fit_records) == config['planned_training_fits']
        assert len(list(source.glob('fit_*.json'))) == len(fit_records)
        assert len(list(source.glob('model_*.pt'))) == len(fit_records)
        assert len(new) == 224000
        keys = ['seed', 'training_fraction', 'regime', 'arm', 'bank', 'condition']
        arms = sorted(combined.arm.unique())
        expected = set(product([t['seed'] for t in config['trials']], config['regimes'], arms, ('software', 'bias_stress'), sorted({key[1] for key in banks})))
        assert len(arms) == 13
        assert set(combined[['seed', 'regime', 'arm', 'bank', 'condition']].itertuples(index=False, name=None)) == expected
        assert not combined.duplicated(['seed', 'regime', 'arm', 'bank', 'condition', 'series_id']).any()
        fractions = {t['seed']: t['fraction'] for t in config['trials']}
        np.testing.assert_array_equal(combined.training_fraction, combined.seed.map(fractions))
        rows = []
        for key, g in combined.groupby(keys):
            bank, condition = key[-2:]
            truth = banks[bank, condition][0].set_index('series_id').final_risk
            assert set(g.series_id) == set(truth.index)
            np.testing.assert_array_equal(g.y, (truth.loc[g.series_id] >= -6).astype(int))
            assert np.isfinite(g.q).all() and g.q.between(0, 1).all()
            np.testing.assert_allclose(g.log_loss, loss(g.y.to_numpy(), g.q.to_numpy()), atol=1e-14, rtol=0)
            np.testing.assert_array_equal(g.review95, g.q >= g.threshold95)
            rows.append(dict(zip(keys, key), **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())))
        metrics = pd.DataFrame(rows)
        for directory in (source, reference, covariance):
            old = pd.read_csv(directory/'metrics.csv')
            actual = metrics[metrics.arm.isin(old.arm.unique())]
            pd.testing.assert_frame_equal(actual.sort_values(keys).reset_index(drop=True)[old.columns],
                old.sort_values(keys).reset_index(drop=True), check_dtype=False, atol=1e-12, rtol=1e-12)
        contrasts, ranges = paired_comparisons(combined)
        loss_ranges, _ = stability_tables(metrics)
        selected = pd.DataFrame([{k: v for k, v in s.items() if k != 'inner_scores'} for s in selections])
        fits = pd.DataFrame([{k: v for k, v in r.items() if k != 'epoch_training_loss'} for r in fit_records])
        for name, data in (('metrics', metrics), ('selections', selected), ('candidate_scores', pd.DataFrame(profiles)),
                           ('fit_records', fits), ('paired_contrasts', contrasts), ('comparison_ranges', ranges), ('loss_ranges', loss_ranges)):
            data.to_csv(run.path/f'{name}.csv', index=False)
        audit = {'source_run': source_audit, 'compatibility': compatibility, 'reconstructed_fits': len(fits),
            'reconstructed_candidate_oof_rows': int(fits.validation_rows.sum()), 'selected_models': len(selected),
            'new_predictions_bitwise_reconstructed': len(new), 'combined_prediction_rows': len(combined),
            'all_candidate_preprocessors_and_oof_reconstructed': True, 'calibration_and_thresholds_reconstructed': True,
            'folds_scenario_weights_and_labels_verified': True, 'all_combined_metrics_reconstructed': True,
            'replay_and_latest_only_invariants_verified': True, 'scientific_bank_opened': False,
            'scope': 'Same-workflow artifact verification; not A03 independent review or confirmatory evaluation.'}
        write_json(run.path/'audit.json', audit)
        sections = []
        full = metrics[metrics.training_fraction == 1]
        for bank, condition in product(('software', 'bias_stress'), ('overlap_90', 'new_information')):
            g = full[(full.regime == 'matched_mixture') & (full.bank == bank) & (full.condition == condition)]
            sections += [f'### Matched training / {bank} / {condition}', '', table(g, ['arm', 'log_loss', 'brier', 'reviewed', 'fn']), '']
        comparisons = ranges[(ranges.regime == 'matched_mixture') & ranges.condition.isin(['overlap_90', 'new_information'])
            & ranges.comparator.isin(['singleton', 'grouped', 'latest_metadata', 'covariance_direct', *ARMS])]
        report = f'''# V02 sequence-family adaptation and latest-only capacity control

Date: 10 October 2026. Source `{source.name}`; reconstruction `{args.run_id}`.
**Exploratory exposed-bank results. V02 remains open; scientific reservation unopened.**

## Method and fixed budget

The [committed contract](../../execution/sequence_contract.md) precedes the first
study fit. Both arms use two unidirectional LSTM layers, dropout 0.2, a final-valid-state
linear readout and BCE. Widths 8/16/32 crossed with 20/60 fixed epochs give six
candidates per arm. Adam uses learning rate .003, gradient norm cap 5, batch size
256, CPU float32 and deterministic algorithms. The 60-dimensional per-message
input contains the common phi fields and missing flags; age codes are categorical.
Packed sequences exclude padding inside recurrence. Chronological ordering and
exact-replay canonicalization precede feature construction. No future rows, IDs,
final labels or oracle lineage enter the input.

The history arm receives the full visible prefix; `lstm_latest` receives only its
last message. Both use training-prefix-only median/robust scaling to match the
preprocessing policy; consequently the latest arm uses training-history distribution
statistics, but no earlier messages from an evaluation event. Checkpoint audit
refits every preprocessor using exactly its fitting rows.

This is a smaller-capacity final-class adaptation of an accessible sequence family,
not Pinto's next-CDM MSE experiment, a published score reproduction or a SOTA claim.
Six candidates match the logistic/proxy candidate count but not their capacity,
optimizer or compute budget. There is no early stopping or outcome-based grid
change. {len(fits)} declared fits completed; {int(selected.epochs.eq(60).sum())}/16
selections use the maximum epoch budget and {int(selected.hidden.eq(32).sum())}/16
use maximum width. Fixed-epoch training does not establish optimizer convergence.
`candidate_scores.csv` and `fit_records.csv` retain every candidate score and
fit runtime/seed; local checkpoints also retain every epoch's training loss.

All variants of a scenario remain together in the three inner folds. Each scenario
contributes objective weight one across its variants. Selected inner OOF scores
are reused for monotone Platt calibration and the nominal 95% training-recall
threshold; this reuse can be optimistic and supplies no risk guarantee. The same
1,000-scenario reference and three overlapping 800-scenario subsets, regimes and
fold assignments are shared with the 88 archived control models. Control reuse
passes data/source/fold compatibility checks; controls receive no new tuning.

## Full-data reference

Each evaluation bank contains 1,000 paired scenarios: software has 194 positives,
bias stress 326. These enriched, unweighted synthetic banks do not estimate
operational prevalence or workload. Forecast q means final recorded-risk class,
not physical collision probability or a maneuver decision. All conditions and
both regimes, including adverse cases, remain in `metrics.csv`.

{chr(10).join(sections)}
## Training sensitivity and paired endpoints

The three 800-scenario subsets overlap; neither these trials nor the repeated
{len(combined):,} prediction rows are independent replications. Ranges below are
descriptive, not confidence intervals. Negative loss differences favor the named
neural arm. A count of three lower-loss trials is not a significance test.

{table(comparisons, ['bank', 'condition', 'arm', 'comparator', 'log_loss_absolute_difference_mean', 'log_loss_absolute_difference_min', 'log_loss_absolute_difference_max', 'neural_lower_loss_seeds'])}

`paired_contrasts.csv` retains scenario-paired absolute and no-reuse-relative
degradation differences for log loss, Brier score, review indicator and missed
positive indicator. Miss differences are conditional on the bank's positive
scenarios; other endpoints average all 1,000 cases. Paired standard deviations
support later precision planning. No multiplicity-adjusted test or frozen primary
comparison is claimed. `loss_ranges.csv` retains per-arm loss, Brier, review-count
and missed-positive-count ranges over the three subsets separately from the full
reference.

## Verification and next work

All {len(fits)} checkpoint metadata/preprocessors and {int(fits.validation_rows.sum()):,}
candidate OOF values reconstruct; selection, calibration and thresholds reproduce.
All {len(new):,} new forecasts reconstruct bitwise from selected checkpoints in
this environment. All 104 models' saved prediction metrics and scenario identities
are checked; earlier control models retain their previous audits. Exact replay
and latest-only invariants pass with the declared float32 tolerance. Safe checkpoint
loading uses `weights_only=True`; cross-platform bitwise equality is not promised.

This is artifact verification, not independent A03 scientific review. Observable-
provenance component ablations and precision planning remain before V03. The
scientific seed 20261012 has not been generated, and no real-data neural efficacy
or superior method conclusion follows automatically from these development tables.
'''
        (run.path/'report.md').write_text(report, encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('report.md', 'metrics.csv', 'selections.csv', 'candidate_scores.csv', 'fit_records.csv',
             'paired_contrasts.csv', 'comparison_ranges.csv', 'loss_ranges.csv', 'audit.json')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name, reference.name, covariance.name],
                  'manifest_sha256': sha256(run.path/'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path/name, args.export/name)
        provenance['artifacts'][name] = sha256(run.path/name)
    write_json(args.export/'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


if __name__ == '__main__':
    main()
