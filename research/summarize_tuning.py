"""Reconstruct common-grid changes and descriptive training-subset sensitivity."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
from itertools import product

import joblib
import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json
from research.metrics import class_metrics, loss
from research.models import policy_threshold
from research.summarize_pilot import audit_run, table


def stability_tables(metrics):
    """Ranges across subsets, never pooling repeated evaluation scenarios as new n."""
    subset = metrics[metrics.training_fraction < 1]
    rows, comparisons = [], []
    keys = ['regime', 'arm', 'bank', 'condition']
    for key, group in subset.groupby(keys):
        if not group.seed.is_unique or group.n.nunique() != 1 or group.positives.nunique() != 1:
            raise ValueError('Repeated/mismatched evaluation units across seed summaries')
        row = dict(zip(keys, key), training_repeats=len(group),
                   evaluation_scenarios=int(group.n.iloc[0]), evaluation_positives=int(group.positives.iloc[0]))
        for column in ('log_loss', 'brier', 'reviewed', 'fn'):
            row.update({f'{column}_mean': float(group[column].mean()),
                        f'{column}_min': float(group[column].min()),
                        f'{column}_max': float(group[column].max())})
        rows.append(row)
    for (regime, bank), group in subset.groupby(['regime', 'bank']):
        p = group.pivot(index='seed', columns=['arm', 'condition'], values='log_loss')
        for condition in group.condition.unique():
            for arm in sorted(set(group.arm)-{'grouped'}):
                absolute = p['grouped', condition]-p[arm, condition]
                degradation = absolute-(p['grouped', 'no_reuse']-p[arm, 'no_reuse'])
                if absolute.isna().any() or degradation.isna().any():
                    raise ValueError('Incomplete paired seed comparison')
                comparisons.append({'regime': regime, 'bank': bank, 'condition': condition,
                    'comparator': arm, 'training_repeats': len(absolute),
                    'absolute_difference_mean': float(absolute.mean()),
                    'absolute_difference_min': float(absolute.min()),
                    'absolute_difference_max': float(absolute.max()),
                    'grouped_lower_loss_seeds': int((absolute < -1e-12).sum()),
                    'degradation_difference_mean': float(degradation.mean()),
                    'degradation_difference_min': float(degradation.min()),
                    'degradation_difference_max': float(degradation.max())})
    return pd.DataFrame(rows), pd.DataFrame(comparisons)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError('Use an exclusive export destination')
    source, previous = args.source.resolve(), args.previous.resolve()
    source_audits = [audit_run(source), audit_run(previous)]
    manifest = json.loads((source/'manifest.json').read_text())
    old_manifest = json.loads((previous/'manifest.json').read_text())
    assert manifest['kind'] == 'expanded_tuning_sensitivity'
    assert old_manifest['kind'] == 'simulation_training_regimes'
    # Both campaigns must derive from the same immutable cadence source.
    old_parquet = {k: v for k, v in old_manifest['inputs'].items() if k.endswith('.parquet')}
    assert old_parquet == {k: v for k, v in manifest['inputs'].items() if k.endswith('.parquet')}
    config = manifest['config']
    with Run(args.run_id, 'expanded_tuning_reconstruction', {'source': str(source), 'previous': str(previous)},
             [source/'manifest.json', previous/'manifest.json']) as run:
        predictions = read_table(source/'predictions.parquet')
        selections = json.loads((source/'selections.json').read_text())
        saved_metrics = pd.read_csv(source/'metrics.csv')
        full_seed = next(t['seed'] for t in config['trials'] if t['fraction'] == 1.)
        assert full_seed == old_manifest['config']['seed']
        expected_models = len(config['trials'])*len(config['regimes'])*len(config['arms'])
        assert len(selections) == expected_models
        expected_model_keys = set(product([t['seed'] for t in config['trials']], config['regimes'], config['arms']))
        assert {(s['seed'], s['regime'], s['arm']) for s in selections} == expected_model_keys
        assert not predictions.duplicated(['seed', 'regime', 'arm', 'bank', 'condition', 'series_id']).any()
        data_source = Path(next(k for k in manifest['inputs'] if k.endswith('cohort_software.parquet'))).parent
        conditions = json.loads((data_source/'manifest.json').read_text())['config']['conditions']
        expected_cells = {(*key, bank, condition) for key in expected_model_keys
                          for bank, condition in product(('software', 'bias_stress'), conditions)}
        actual_cells = set(predictions[['seed', 'regime', 'arm', 'bank', 'condition']].itertuples(index=False, name=None))
        assert actual_cells == expected_cells
        assert np.isfinite(predictions.q).all() and predictions.q.between(0, 1).all()
        fractions = {trial['seed']: trial['fraction'] for trial in config['trials']}
        np.testing.assert_array_equal(predictions.training_fraction, predictions.seed.map(fractions))
        for (_, _, arm, _), g in predictions.groupby(['seed', 'regime', 'arm', 'bank']):
            pivot = g.pivot(index='series_id', columns='condition', values='q')
            np.testing.assert_allclose(pivot.no_reuse, pivot.exact_replay, rtol=0, atol=1e-12)
            if arm in ('latest', 'latest_metadata'):
                for condition in ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue'):
                    np.testing.assert_allclose(pivot.no_reuse, pivot[condition], rtol=0, atol=1e-12)
        development = read_table(data_source/'cohort_development.parquet').set_index('series_id')
        for bank in predictions.bank.unique():
            truth = read_table(data_source/f'cohort_{bank}.parquet').set_index('series_id').final_risk
            for _, g in predictions[predictions.bank == bank].groupby(['seed', 'regime', 'arm', 'condition']):
                assert g.series_id.is_unique and set(g.series_id) == set(truth.index)
                np.testing.assert_array_equal(g.y, (truth.loc[g.series_id] >= -6).astype(int))
        keys = ['seed', 'training_fraction', 'regime', 'arm', 'bank', 'condition']
        rows = []
        for key, g in predictions.groupby(keys):
            np.testing.assert_allclose(g.log_loss, loss(g.y.to_numpy(), g.q.to_numpy()), rtol=0, atol=1e-14)
            assert np.array_equal(g.review95, g.q >= g.threshold95)
            rows.append(dict(zip(keys, key), **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())))
        metrics = pd.DataFrame(rows)
        pd.testing.assert_frame_equal(metrics.sort_values(keys).reset_index(drop=True)[saved_metrics.columns],
            saved_metrics.sort_values(keys).reset_index(drop=True), check_dtype=False, atol=1e-12, rtol=1e-12)
        memberships, cohorts = {}, {}
        for trial in config['trials']:
            seed = trial['seed']
            c = read_table(source/f'cohort_seed{seed}.parquet')
            assert c.series_id.is_unique
            assert set(c.series_id) <= set(development.index)
            np.testing.assert_array_equal(c.final_risk, development.loc[c.series_id].final_risk)
            for positive in (False, True):
                expected = int(np.floor(trial['fraction']*((development.final_risk >= -6) == positive).sum()))
                assert int(((c.final_risk >= -6) == positive).sum()) == expected
            cohorts[seed] = set(c.series_id)
            fold_maps = []
            for regime, conditions in config['regimes'].items():
                f = read_table(source/f'training_seed{seed}_{regime}.parquet')
                assert set(f.series_id) == cohorts[seed] and set(f.condition) == set(conditions)
                assert not f.duplicated(['series_id', 'condition']).any()
                assert (f.groupby('series_id').size() == len(conditions)).all()
                assert (f.groupby('series_id').inner_fold.nunique() == 1).all()
                assert set(f.inner_fold) == set(range(config['inner_folds']))
                np.testing.assert_array_equal(f.y, (development.loc[f.series_id].final_risk >= -6).astype(int))
                np.testing.assert_allclose(f.groupby('series_id').event_weight.sum(), 1.)
                fold_maps.append(f.groupby('series_id').inner_fold.first())
                memberships[seed, regime] = f
            pd.testing.assert_series_equal(*fold_maps)
        profile, chosen = [], []
        for selection in selections:
            seed, regime, arm = selection['seed'], selection['regime'], selection['arm']
            prefix = f'seed{seed}_{regime}_{arm}'
            f = memberships[seed, regime]
            oof = read_table(source/f'oof_{prefix}.parquet')
            pd.testing.assert_frame_equal(oof.drop(columns='raw_oof'), f)
            assert np.isfinite(oof.raw_oof).all()
            fitted = joblib.load(source/f'model_{prefix}.joblib')
            q = fitted['calibration'].predict(oof.raw_oof.to_numpy())
            assert policy_threshold(q, oof.y.to_numpy(), .95) == fitted['threshold95'] == selection['threshold95']
            prediction_thresholds = predictions.loc[(predictions.seed == seed) &
                (predictions.regime == regime) & (predictions.arm == arm), 'threshold95']
            assert (prediction_thresholds == selection['threshold95']).all()
            assert selection['training_fraction'] == fractions[seed]
            assert selection['training_scenarios'] == len(cohorts[seed])
            assert selection['training_variant_rows'] == len(f)
            scores = {float(c): v for c, v in selection['inner_scores'].items()}
            assert sorted(scores) == config['C']
            assert min(scores, key=lambda c: (scores[c], c)) == selection['C']
            assert np.isclose(np.average(loss(oof.y.to_numpy(), oof.raw_oof.to_numpy()), weights=oof.event_weight),
                              scores[selection['C']], atol=1e-14, rtol=0)
            assert selection['convergence_required'] and selection['maximum_observed_iterations'] < selection['max_iter']
            chosen.append({k: v for k, v in selection.items() if k != 'inner_scores'})
            for c, score in scores.items():
                profile.append({'seed': seed, 'regime': regime, 'arm': arm, 'C': c,
                    'inner_oof_log_loss': score, 'selected': c == selection['C']})
        selected = pd.DataFrame(chosen)
        selected.to_csv(run.path/'selections.csv', index=False)
        pd.DataFrame(profile).to_csv(run.path/'candidate_scores.csv', index=False)
        metrics.to_csv(run.path/'metrics.csv', index=False)
        ranges, comparisons = stability_tables(metrics)
        ranges.to_csv(run.path/'subset_ranges.csv', index=False)
        comparisons.to_csv(run.path/'grouped_comparisons.csv', index=False)
        old = pd.read_csv(previous/'metrics.csv')
        reference = metrics[metrics.seed == full_seed]
        join = ['regime', 'arm', 'bank', 'condition']
        changes = reference.merge(old, on=join, suffixes=('_expanded', '_previous'), validate='one_to_one')
        for metric in ('log_loss', 'brier', 'reviewed', 'fn'):
            changes[f'{metric}_change'] = changes[f'{metric}_expanded']-changes[f'{metric}_previous']
        changes[join+[f'{m}_{s}' for m in ('log_loss', 'brier', 'reviewed', 'fn')
                      for s in ('previous', 'expanded', 'change')]].to_csv(run.path/'reference_grid_change.csv', index=False)
        overlaps = []
        seeds = [t['seed'] for t in config['trials'] if t['fraction'] < 1]
        for i, a in enumerate(seeds):
            for b in seeds[i+1:]:
                overlaps.append({'seed_a': a, 'seed_b': b, 'intersection': len(cohorts[a]&cohorts[b]),
                                 'union': len(cohorts[a]|cohorts[b])})
        audit = {'source_runs': source_audits, 'selected_models': len(selections),
            'prediction_rows': len(predictions), 'class_metrics_reconstructed': True,
            'selected_oof_losses_and_thresholds_reconstructed': True, 'same_scenario_folds_across_arms_and_regimes': True,
            'scenario_weights_one': True, 'candidate_grid_equal': True,
            'all_convergence_checks_passed': True, 'training_subset_overlap': overlaps,
            'replay_and_matched_latest_reconstructed': True,
            'scientific_reserved_bank_opened': False,
            'limits': 'Three overlapping training subsets; candidate aggregate OOF losses retained for all C, event-level OOF predictions retained for selected C; no independent scientific replication.'}
        write_json(run.path/'audit.json', audit)
        bound = selected.groupby(['regime', 'arm']).agg(fits=('C', 'size'), min_C=('C', 'min'), max_C=('C', 'max'))
        bound['upper_boundary_fits'] = selected.assign(edge=selected.C == max(config['C'])).groupby(['regime', 'arm']).edge.sum()
        bound = bound.reset_index()
        bound.to_csv(run.path/'grid_boundaries.csv', index=False)
        display = ranges.merge(reference[join+['log_loss']], on=join, validate='one_to_one').rename(columns={'log_loss': 'full_data_loss'})
        sections = []
        for bank in ('software', 'bias_stress'):
            for condition in ('overlap_90', 'new_information'):
                g = display[(display.regime == 'matched_mixture') & (display.bank == bank) & (display.condition == condition)]
                sections += [f'### Matched training / {bank} / {condition}',
                    table(g, ['arm', 'full_data_loss', 'log_loss_mean', 'log_loss_min', 'log_loss_max', 'fn_min', 'fn_max'])]
        key_comparisons = comparisons[(comparisons.regime == 'matched_mixture') &
            comparisons.condition.isin(['overlap_90', 'new_information']) &
            comparisons.comparator.isin(['latest_metadata', 'singleton', 'thin'])]
        upper = int((selected.C == max(config['C'])).sum())
        report = f'''# V02 expanded tuning and training-subset sensitivity

Date: 9 October 2026. Runs: `{source.name}`, prior reference `{previous.name}`, reconstruction `{args.run_id}`. **Exploratory development evidence; V02 remains open.** No reserved scientific scenarios were generated or inspected.

## What was varied

Every predictor uses C in {config['C']} and a common {config['max_iter']:,}-iteration cap. There are nine predictors, two training regimes, and four trials: the full 1,000-scenario reference at seed {full_seed}, then three stratified 800-scenario subsets at seeds {seeds}. The smaller subsets each have 144 positives; the original development bank has 180. They are overlapping selections from the same bank, not new independent cohorts. Changing a deterministic solver seed alone would not establish training variability.

The same scenarios, inner folds and candidate grid are used across predictors and regimes within each trial. All history variants of a scenario stay together. Each selected scenario contributes one total objective unit. Calibration and the nominal recall threshold use selected inner-OOF predictions; their reuse is recorded and no risk certificate is claimed. All {len(selections)} fits converged, with a maximum observed {int(selected.maximum_observed_iterations.max())} iterations. Source checkpoints retain models, selected-C OOF predictions and aggregate candidate losses. {len(predictions):,} evaluation rows refer to the same 1,000 scenarios per exposed evaluation bank, repeated across configurations.

## Tuning boundary

{upper}/{len(selected)} selected fits still choose the upper C boundary. Interior choices show where the old cap of 10 constrained selection. Boundary choices remain a limitation; extending a finite grid does not prove optimal tuning. The larger optimizer cap is shared by all arms. Do not describe the change as a new model or a scientific confirmation.

{table(bound, ['regime', 'arm', 'fits', 'min_C', 'max_C', 'upper_boundary_fits'])}

`reference_grid_change.csv` compares the new full-data trial with the preceding campaign on identical evaluation cells. It separates the common-grid/optimizer-cap change from the smaller training subsets. Each cell includes previous/new log loss, Brier score, review count and missed-positive count. Do not attribute the difference between 1,000-scenario and 800-scenario training solely to a random seed.

## Descriptive sensitivity ranges

The mean/min/max columns summarize the **three equal-size training subsets only**. Full-data loss is displayed separately. Ranges are not confidence intervals; three overlapping subsets are insufficient for a precise training-uncertainty estimate. Miss counts are out of 194 software positives or 326 bias-stress positives, not out of repeated prediction rows. The synthetic prevalence is enriched and unweighted; it is not an operational workload estimate.

{chr(10).join(sections)}

## Does grouping reliably improve on simple controls?

Differences are grouped minus comparator: negative favors grouping. `grouped_lower_loss_seeds` counts the three subset trials; it is not a statistical significance test. All conditions and controls, including the shifted regime, are retained in the companion CSV.

{table(key_comparisons, ['bank','condition','comparator','absolute_difference_mean','absolute_difference_min','absolute_difference_max','grouped_lower_loss_seeds'])}

Absolute loss and overlap-induced degradation are separate endpoints. `grouped_comparisons.csv` also reports the difference in no-reuse-to-condition degradation. A smaller degradation does not guarantee a lower absolute loss. Never pool training subsets, message variants or seeds to increase the independent evaluation count.

## What this permits next

This campaign checks the common tuning range and membership/fold sensitivity for the existing model family. It does not reproduce the covariance-weighting or sequence papers, complete component/oracle ablations, establish a primary comparator, or supply a scientific sample-size calculation. Those are the remaining V02 tasks. Preserve adverse bias-stress and ranking changes; do not select a flattering condition for the paper.

Next implement the explicitly labeled covariance-proxy comparator and ablations with the same fold/budget contract; add state-fusion/oracle diagnostics separately from class forecasting. Use the resulting paired scenario and training-variation evidence for precision planning. V03 must freeze the scientific study before the reserved bank is opened.

## Verification and portability

`audit.json` records source/input/output/archive checksums, full prediction coverage and labels, scenario folds/weights, every class metric, all selected-OOF losses, all {len(selected)} thresholds, and equal candidate budgets. The campaign checks replay and matched-latest invariance for every fitted model. This is artifact reconstruction, not A03's independent scientific review.

The compact files preserve source artifact bytes via Git attributes. `provenance.json` maps exports to this reconstruction run. Models, full predictions, datasets and logs remain ignored/local. Exact regeneration requires the run/data transfer described in the root checklist.
'''
        (run.path/'report.md').write_text(report, encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('report.md', 'metrics.csv', 'selections.csv', 'candidate_scores.csv', 'subset_ranges.csv',
             'grouped_comparisons.csv', 'reference_grid_change.csv', 'grid_boundaries.csv', 'audit.json')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name, previous.name],
                  'manifest_sha256': sha256(run.path/'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path/name, args.export/name)
        provenance['artifacts'][name] = sha256(run.path/name)
    write_json(args.export/'provenance.json', provenance)
    print('Exported audited tuning and sensitivity results:', args.export, flush=True)


if __name__ == '__main__':
    main()
