"""Audit and export the cadence/training-regime development comparison."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil

import joblib
import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json
from research.metrics import class_metrics
from research.models import policy_threshold
from research.summarize_pilot import audit_run, table


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--cadence-source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError('Use a new export directory')
    source, cadence = args.source.resolve(), args.cadence_source.resolve()
    audits = [audit_run(source), audit_run(cadence)]
    config = {'source': str(source), 'cadence_source': str(cadence),
              'scope': 'Exploratory reconstruction; no training or new scenario generation'}
    with Run(args.run_id, 'training_regime_synthesis', config,
             [source/'manifest.json', cadence/'manifest.json']) as run:
        predictions = read_table(source/'predictions.parquet')
        metrics = json.loads((source/'metrics.json').read_text())
        assert not predictions.duplicated(['regime', 'arm', 'bank', 'condition', 'series_id']).any()
        models = []
        for key, g in predictions.groupby(['regime', 'arm', 'bank', 'condition']):
            assert class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy()) == metrics['models']['/'.join(key)]
            models.append(dict(zip(('regime', 'arm', 'bank', 'condition'), key), **metrics['models']['/'.join(key)]))
        for bank in predictions.bank.unique():
            cohort = read_table(cadence/f'cohort_{bank}.parquet').set_index('series_id')
            for _, g in predictions[predictions.bank == bank].groupby(['regime', 'arm', 'condition']):
                assert set(g.series_id) == set(cohort.index)
                np.testing.assert_array_equal(g.y, (cohort.loc[g.series_id].final_risk >= -6).astype(int))
        split_maps, training = {}, {}
        for regime in predictions.regime.unique():
            membership = read_table(source/f'training_{regime}.parquet')
            assert not membership.duplicated(['series_id', 'condition']).any()
            assert (membership.groupby('series_id').inner_fold.nunique() == 1).all()
            np.testing.assert_allclose(membership.groupby('series_id').event_weight.sum(), 1.)
            split_maps[regime] = membership.groupby('series_id').inner_fold.first()
            training[regime] = {'scenarios': int(membership.series_id.nunique()),
                'variant_rows': len(membership), 'positives': int(membership.drop_duplicates('series_id').y.sum())}
            for arm in predictions.arm.unique():
                oof = read_table(source/f'oof_{regime}_{arm}.parquet')
                pd.testing.assert_frame_equal(oof.drop(columns='raw_oof'), membership)
                assert np.isfinite(oof.raw_oof).all()
                fitted = joblib.load(source/f'model_{regime}_{arm}.joblib')
                q = fitted['calibration'].predict(oof.raw_oof.to_numpy())
                assert policy_threshold(q, oof.y.to_numpy(), .95) == fitted['threshold95']
        pd.testing.assert_series_equal(split_maps['no_reuse_only'], split_maps['matched_mixture'])
        frame = pd.DataFrame(models)
        frame.to_csv(run.path/'metrics.csv', index=False)
        # Reconstruct paired point estimates; stored intervals retain the original
        # fixed-model bootstrap scope and seed rather than implying replication.
        differences = []
        for (arm, bank, condition), g in predictions.groupby(['arm', 'bank', 'condition']):
            p = g.pivot(index='series_id', columns='regime', values='log_loss')
            contrast = metrics['matched_minus_shifted'][f'{arm}/{bank}/{condition}']
            assert np.isclose((p.matched_mixture-p.no_reuse_only).mean(), contrast['mean'], rtol=0, atol=1e-14)
            differences.append({'arm': arm, 'bank': bank, 'condition': condition,
                'matched_minus_shifted': contrast['mean'], 'ci_low': contrast['ci95_percentile'][0],
                'ci_high': contrast['ci95_percentile'][1]})
        differences = pd.DataFrame(differences)
        differences.to_csv(run.path/'regime_differences.csv', index=False)
        write_json(run.path/'contrasts.json', {'degradation': metrics['degradation_contrasts'],
            'matched_minus_shifted': metrics['matched_minus_shifted'], 'evidence': metrics['evidence']})
        observed = {}
        for (regime, bank, condition), g in predictions.groupby(['regime', 'bank', 'condition']):
            p = g.pivot(index='series_id', columns='arm', values='q')
            observed[f'{regime}/{bank}/{condition}'] = {
                arm: float(np.max(np.abs(p[arm]-p.singleton))) for arm in ('fixed', 'thin', 'change')}
        write_json(run.path/'control_prediction_differences.json', observed)
        construction = json.loads((cadence/'control_diagnostics.json').read_text())
        write_json(run.path/'construction_checks.json', construction)
        audit = {'source_runs': audits, 'prediction_rows': len(predictions), 'training': training,
            'metrics_reconstructed': True, 'whole_scenario_folds_and_unit_weights': True,
            'same_scenario_folds_across_regimes': True, 'all_18_thresholds_reconstructed': True,
            'exact_replay_check': metrics['exact_replay_check'],
            'matched_latest_message_check': metrics['matched_latest_message_check'],
            'scientific_reserved_bank_opened': False,
            'independent_scientific_reproduction': False}
        write_json(run.path/'audit.json', audit)
        losses = frame.pivot(index=['regime', 'bank', 'arm'], columns='condition', values='log_loss').reset_index()
        sections = []
        for (regime, bank), group in losses.groupby(['regime', 'bank']):
            sections += [f'### {regime} / {bank}', table(group, ['arm', 'no_reuse', 'overlap_90', 'burst_reissue', 'new_information'])]
        new = differences[differences.condition == 'new_information']
        upper_grid = max(json.loads((source/'manifest.json').read_text())['config']['C'])
        boundary_count = sum(s['C'] == upper_grid for s in metrics['selections'])
        decision = []
        for bank, g in new.groupby('bank'):
            decision.append(f"{bank}: matched training lowers new-information loss for {int((g.matched_minus_shifted < 0).sum())}/{len(g)} arms.")
        report = f'''# V02 cadence and training-regime development results

Date: 9 October 2026. Source runs: `{cadence.name}`, `{source.name}`; synthesis: `{args.run_id}`. This is **exposed development evidence**, not a frozen or independent scientific test. V02 remains incomplete.

## Design and construction checks

The same 1,000 latent scenarios in each first-pilot bank were reused: development has 180 positives, software 194 and shared-bias stress 326. Their observation arrays and final labels were not regenerated. The new cadence has unequal short clusters and long gaps. A burst-reissue condition repeats six solutions at ten publication times without new observations. Latest messages remain matched across reuse conditions; age categories are recomputed at publication time.

Before fitting, 128 development scenarios were checked without using labels. All 128 produced nonuniform fixed-time summaries. Thinning retained 3-4 of six ordinary messages, or 5-6 of ten burst messages. Change selection reduced every ten-message burst to six solutions. These are construction distinctions, not claims that every fitted control must predict differently. Actual maximum differences from singleton predictions are saved in `control_prediction_differences.json`.

## Training and evaluation

Nine arms are evaluated under two regimes. `no_reuse_only` uses one history per scenario. `matched_mixture` uses six histories per scenario: no reuse, 50%/90% overlap, solution reissue, cumulative new information and burst reissue. Exact replay is an evaluation/property control, not extra training weight.

All variants stay in one of the same three inner scenario folds. Each latent scenario has total logistic objective weight one, distributed across variants and candidate partitions. Both regimes therefore have 1,000 objective units, although the mixture has 6,000 rows. Imputation and scaling remain training-only; they are unweighted transformations of the training messages/design rows. C is chosen from 0.01, 0.1, 1 and 10 using inner out-of-fold loss. Calibration and the nominal 95% recall threshold use the selected inner predictions; evaluation uses different exposed scenarios. The mixture threshold targets its uniform condition mixture, not 95% recall within every condition.

The latest-metadata arm closes the extra-field mismatch in the first simulation pilot. All nine arms pass exact-replay equality; both latest-message baselines give equal outputs when their latest input is unchanged. No model failed, and {len(predictions):,} event/arm/condition/regime prediction rows are retained. Variant rows are not independent scenarios.

**Tuning limitation:** {boundary_count}/{len(metrics['selections'])} fits selected the upper C-grid boundary ({upper_grid:g}). Before final model selection, V02 should assess a common expanded grid using development-only data and an equal budget for every relevant arm. This pilot does not establish that any arm is optimally tuned.

## Absolute class log loss

Lower is better. Labels are final recorded synthetic risk classes; scores are class probabilities, not physical collision probabilities. Synthetic prevalence is deliberately enriched; these are unweighted stress-distribution results. Tables show selected conditions; `metrics.csv` contains all conditions, Brier/AP/AUC and explicit review/miss counts.

{chr(10).join(sections)}

## Does matched training repair the new-information control?

{' '.join(decision)} Negative contrasts below favor matched training. These comparisons are paired by scenario and conditional on the two fitted models; they do not include training-seed variability or multiplicity correction.

{table(new, ['bank','arm','matched_minus_shifted','ci_low','ci_high'])}

A decrease in loss under matched training diagnoses sensitivity to the training regime. It does not prove that grouping is superior, that all additional observations improve every learned forecast, or that the simulator captures operational dynamics. Compare absolute loss against latest-metadata and simple controls before attributing a benefit to dependence treatment. The oracle state-error improvement documented in the original synthesis remains a separate physical-information diagnostic.

## Interpretation and remaining work

The repair removes the pilot's construction-level control collapse and explicitly tests the prior training-distribution mismatch. All positive, negative and null comparisons remain in the exported tables. The original pilot is preserved; this revision was informed by it and must not be called confirmation.

Next V02 work: covariance-proxy and sequence-family adaptations with declared budgets, separate state-fusion/unique-observation-oracle diagnostics, component/provenance ablations, training-seed sensitivity, and precision planning. V03 must then select and freeze one justified primary comparison before accessing the reserved scientific scenarios. Seed 20261012 and the reserved scientific bank remain unopened.

## Reconstruction

`research.summarize_regimes` checks completed source manifests and hashes, prediction coverage/labels, scenario folds and weights, all saved class metrics and all 18 training thresholds. It does not retrain or open new outcomes. `audit.json` records the checks. This is same-assistant artifact reconstruction, not the independent scientific review required by A03.

The compact export has original artifact hashes and source run IDs. Raw data, PDFs, predictions, models, source archives and process logs remain local/ignored. Existing binaries and predictions must be transferred separately for exact reproduction on another machine.
'''
        (run.path/'report.md').write_text(report, encoding='utf-8')
    # Export only after the reconstruction run is complete, preserving byte hashes.
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('report.md', 'metrics.csv', 'regime_differences.csv', 'contrasts.json',
             'control_prediction_differences.json', 'construction_checks.json', 'audit.json')
    provenance = {'run_id': args.run_id, 'source_runs': [cadence.name, source.name],
        'manifest_sha256': sha256(run.path/'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path/name, args.export/name)
        provenance['artifacts'][name] = sha256(run.path/name)
    write_json(args.export/'provenance.json', provenance)
    print('Reconstructed and exported development results:', args.export, flush=True)


if __name__ == '__main__':
    main()
