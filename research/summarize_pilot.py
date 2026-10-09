"""Reconstruct exploratory pilot tables and audit their saved provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import joblib
import numpy as np
import pandas as pd

from research.artifacts import ROOT, RUN_ROOT, Run, read_table, sha256, write_json, write_table
from research.history import PHI_NAMES, events_from_frame
from research.metrics import class_metrics, loss, official_metrics
from research.simulation import NOISE_VARIANCE, posterior


def audit_run(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError(f'Incomplete input: {path.name}')
    for name, record in manifest['artifacts'].items():
        if sha256(path / name) != record['sha256']:
            raise ValueError(f'Artifact checksum mismatch: {path.name}/{name}')
    for name, expected in manifest['inputs'].items():
        if sha256(Path(name)) != expected:
            raise ValueError(f'Input checksum mismatch: {path.name}/{name}')
    with zipfile.ZipFile(path / 'code_snapshot.zip') as archive:
        for name, expected in manifest['code_sha256'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected:
                raise ValueError(f'Archived source checksum mismatch: {name}')
    return {'run_id': path.name, 'status': 'complete',
            'artifacts_verified': len(manifest['artifacts']),
            'inputs_verified': len(manifest['inputs']),
            'archived_sources_verified': len(manifest['code_sha256'])}


def table(frame, columns):
    def display(value):
        return f'{value:.6f}' if isinstance(value, (float, np.floating)) else str(value)
    return '\n'.join(['| ' + ' | '.join(columns) + ' |',
                      '| ' + ' | '.join(['---'] * len(columns)) + ' |',
                      *['| ' + ' | '.join(display(v) for v in row) + ' |'
                        for row in frame[columns].itertuples(index=False, name=None)]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--cv-run', default='cv_20261009_v2')
    parser.add_argument('--data-run', default='data_20261009_v2')
    parser.add_argument('--two-stage-run', default='two_stage_20261009_v1')
    parser.add_argument('--simulation-run', default='simulation_20261009_v1')
    parser.add_argument('--mechanism-run', default='mechanism_20261009_v1')
    args = parser.parse_args()
    sources = {k: RUN_ROOT / getattr(args, k + '_run')
               for k in ('cv', 'data', 'two_stage', 'simulation', 'mechanism')}
    audit = [audit_run(p) for p in sources.values()]
    inputs = [p / 'manifest.json' for p in sources.values()]
    with Run(args.run_id, 'pilot_synthesis_and_integrity_audit', vars(args), inputs) as run:
        run.access('saved development predictions and synthetic truth',
                   'reconstruct tables; exploratory diagnostics', 'no reserved scientific outcomes accessed')
        cv = read_table(sources['cv'] / 'predictions.parquet')
        split = read_table(sources['cv'] / 'splits.parquet')
        cohort = read_table(sources['cv'] / 'cohort.parquet')
        outer = split[split.role == 'outer_evaluation']
        assert len(outer) == len(cohort) and outer.series_id.is_unique
        for k in outer.outer_fold.unique():
            ev = set(outer.loc[outer.outer_fold == k, 'series_id'])
            iv = split[(split.outer_fold == k) & (split.role == 'inner_validation')]
            assert iv.series_id.is_unique and not ev & set(iv.series_id)
            assert ev | set(iv.series_id) == set(cohort.series_id)
        stored = json.loads((sources['cv'] / 'metrics.json').read_text())['models']
        real_rows = []
        for arm, g in cv.groupby('arm'):
            assert g.series_id.is_unique and set(g.series_id) == set(cohort.series_id)
            assert not g.failure.any()
            for target in (90, 95, 99):
                m = class_metrics(g.y.to_numpy(), g.q.to_numpy(), g[f'review_{target}'].to_numpy())
                assert m == stored[arm][str(target)]
                real_rows.append({'arm': arm, 'nominal_recall_target': target, **m})
        real = pd.DataFrame(real_rows)
        real.to_csv(run.path / 'real_cv_metrics.csv', index=False)
        # Paired point estimates only: ordinary event bootstrap would ignore
        # overlapping CV training sets and uncertain object/mission dependence.
        pivot = cv.assign(log_loss=loss(cv.y.to_numpy(), cv.q.to_numpy())).pivot(
            index='series_id', columns='arm', values='log_loss')
        contrasts = {arm: float((pivot.grouped - pivot[arm]).mean())
                     for arm in pivot.columns if arm != 'grouped'}
        write_json(run.path / 'real_paired_loss_differences.json', {
            'grouped_minus_comparator': contrasts,
            'uncertainty': 'Point estimates only; no independent-event confidence claim from overlapping training folds.'})

        # Save actual partition scores from each held-out grouped-model fold.
        visible = read_table(sources['data'] / 'visible_train.parquet')
        diagnostics = []
        for k, g in cv[cv.arm == 'grouped'].groupby('outer_fold'):
            fitted = joblib.load(sources['cv'] / f'model_grouped_fold{k}.joblib')
            events = events_from_frame(visible, g.series_id.tolist())
            design, owners, weights = fitted['model'].history.transform(events)
            raw = fitted['model'].model.predict_proba(design)[:, 1]
            component_q = fitted['calibrator'].predict(raw)
            maximum = np.full(len(g), -np.inf)
            np.maximum.at(maximum, owners, component_q)
            np.testing.assert_allclose(maximum, g.q, rtol=1e-12, atol=1e-12)
            diag = pd.DataFrame({'series_id': g.series_id.to_numpy()[owners],
                'outer_fold': k, 'raw_partition_score': raw, 'calibrated_component': component_q,
                'event_weight': weights, 'group_count': design[:, 3 * len(PHI_NAMES) + 1]})
            diag['partition_index'] = diag.groupby('series_id').cumcount()
            diagnostics.append(diag)
        diag = pd.concat(diagnostics, ignore_index=True)
        write_table(run.path / 'partition_diagnostics.parquet', diag)
        ranges = diag.groupby('series_id').calibrated_component.agg(['min', 'max', 'count']).reset_index()
        ranges['sensitivity_width'] = ranges['max'] - ranges['min']
        write_table(run.path / 'partition_sensitivity.parquet', ranges)

        mechanism = json.loads((sources['mechanism'] / 'metrics.json').read_text())
        sim_rows = []
        for key, value in mechanism['models'].items():
            arm, bank, condition = key.split('/')
            sim_rows.append({'arm': arm, 'bank': bank, 'condition': condition, **value})
        sim = pd.DataFrame(sim_rows)
        sim.to_csv(run.path / 'simulation_metrics.csv', index=False)
        write_json(run.path / 'simulation_contrasts.json', mechanism['contrasts'])
        sim_predictions = read_table(sources['mechanism'] / 'predictions.parquet')
        for (arm, bank, condition), g in sim_predictions.groupby(['arm', 'bank', 'condition']):
            assert len(g) == 1000 and g.series_id.is_unique
            assert class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy()) == mechanism['models'][f'{arm}/{bank}/{condition}']
        equality = {}
        for bank in ('software', 'bias_stress'):
            p = sim_predictions[sim_predictions.bank == bank].pivot(
                index=['series_id', 'condition'], columns='arm', values='q')
            equality[bank] = {a: float(np.max(np.abs(p[a] - p.singleton)))
                              for a in ('fixed', 'thin', 'change')}
        write_json(run.path / 'control_equivalence.json', equality)

        official = json.loads((sources['two_stage'] / 'metrics.json').read_text())
        official_rows = pd.DataFrame([{'arm': k, **v} for k, v in official['models'].items()])
        official_rows.to_csv(run.path / 'two_stage_metrics.csv', index=False)
        # More unique observations should reduce state error. This diagnostic
        # cannot establish usefulness of a classifier outside its training range.
        oracle = []
        for bank in ('software', 'bias_stress'):
            truth = np.load(sources['simulation'] / f'truth_{bank}.npz')
            R = np.eye(2) * NOISE_VARIANCE
            B = np.eye(2) * (.01 if bank == 'bias_stress' else 0.)
            for count in (10, 60):
                means = np.array([posterior(obs[:count], R, B)[0] for obs in truth['observations']])
                oracle.append({'bank': bank, 'unique_observations': count,
                    'mean_squared_state_error': float(np.mean(np.sum((means-truth['states'])**2, axis=1))),
                    'population': 'unweighted enriched stress scenarios'})
        oracle = pd.DataFrame(oracle)
        oracle.to_csv(run.path / 'new_information_state_check.csv', index=False)
        snapshot = json.loads((ROOT / 'docs/research/execution/workspace_snapshot_2026-10-09.json').read_text())
        protected = []
        for category in ('raw_files', 'historical_artifacts'):
            for item in snapshot[category]:
                assert sha256(ROOT / item['path']) == item['sha256'], item['path']
                protected.append(item['path'])
        for name, item in snapshot['frozen_files'].items():
            actual = subprocess.check_output(['git', 'hash-object', name], cwd=ROOT, text=True).strip()
            assert actual == item['expected'], name
        write_json(run.path / 'integrity_audit.json', {'runs': audit,
            'raw_and_historical_files_unchanged': len(protected), 'frozen_files_unchanged': len(snapshot['frozen_files']),
            'real_prediction_rows': len(cv), 'outer_inner_event_disjoint': True,
            'metrics_reconstructed': True, 'partition_max_reconstructed': True,
            'scientific_reserved_outcomes_opened': False})
        decision = {'decision': 'NARROW', 'route': 'Track R robustness/measurement benchmark; proposed method remains a candidate',
            'reason': 'Mixed pilot performance, indistinguishable synthetic controls, and new-information distribution shift preclude a method-superiority claim.',
            'next_falsifiable_claim': 'With fixed final labels and matched latest messages, increasing observation reuse degrades a history model more than latest-only prediction; grouping must be assessed against absolute loss and distinct thinning/time controls.',
            'next_tasks': ['V01 closest-work compatibility review', 'V02 nondegenerate cadence controls, matched new-information training, oracle lineage ablation, and precision planning'],
            'no_claims': ['operational efficacy', 'physical collision probability prediction', 'one-percent miss guarantee', 'novelty established', 'scientific confirmation']}
        write_json(run.path / 'feasibility.json', decision)
        small = real[real.nominal_recall_target == 95]
        sim_table = sim.pivot(index=['bank', 'arm'], columns='condition', values='log_loss').reset_index()
        report = f'''# First research-cycle feasibility decision

Date: 9 October 2026. Decision: **NARROW**. Retain Track R as a controlled robustness/measurement study. Keep the proposed grouping model as a candidate, not an established improvement. These are exploratory development results; no publishable superiority or operational safety claim follows yet.

## Evidence and boundaries

Synthesis run: `processed/research/{args.run_id}`. Inputs: {', '.join('`'+p.name+'`' for p in sources.values())}. Every source run is complete; input, output, and archived source checksums were verified. Real-data analysis uses the already exposed 8,293-event/66-positive training cohort, with one outer-fold prediction per event per arm. All 11 arms use the same five outer folds and three inner folds. Each model's imputation/scaling, tuning, calibration and nominal policy threshold use only its outer training partition. Inner out-of-fold labels are reused for model selection and calibration/threshold fitting; outer evaluation remains disjoint. This is retrospective model development, not an independent confirmation.

The full-column crosswalk reconciles 189,285 released rows over 102 non-ID fields. Previously unmatched fingerprints were rounding-sensitive; no full-column differences or unresolved matches remain under the declared tolerances. Real metadata gives provenance proxies, not true observation identity. Causal feature extraction does not remove retrospective cohort eligibility.

## Real-data class forecast

The outcome is final recorded log-risk >= -6. `q` is a forecast of that class, not physical collision probability. The table uses a **nominal 95% training recall target**; observed outer-fold misses show why it is not a guarantee. `fn` counts missed positives out of 66, and `reviewed` counts events out of 8,293.

{table(small, ['arm','log_loss','brier','average_precision','reviewed','fn','miss_rate'])}

The companion CSV includes 90%, 95%, and 99% nominal thresholds. No model was selected using historical test performance. Grouped-minus-comparator paired loss point estimates are saved separately; no ordinary independent-event interval is asserted for overlapping training folds or unresolved object-level dependence. Partition score ranges are saved as sensitivity diagnostics, **not uncertainty coverage**.

## Corrected official-score comparison

This is a separate log-risk prediction endpoint, with lower official loss L preferred. B5 cross-fits both classifier and high-risk regressor for threshold selection. The five-fold campaign is new; the historical two-split file is preserved, not relabeled complete. Scores below pool one prediction per event before computing L; they are not the mean of nonlinear fold scores.

{table(official_rows, ['arm','L','mse_hr','f2','tp','fp','fn'])}

The corrected two-stage model does not beat B1 on this endpoint. B4's very low recall makes it particularly unsuitable as a triage result. The historical exposed-test B1 anchor remains 0.6939612612 on 2,167 events; it is a different cohort from the table above.

## Controlled reuse mechanism

Models train on 1,000 no-reuse development scenarios. Each evaluation bank has 1,000 independent latent scenarios with paired variants and common final labels; the software bank has 194 positives and the shared-bias bank 326. Each has six visible messages; exact replay adds identical copies. Overlap conditions share the same latest observation window. Synthetic prevalence is deliberately enriched and the numbers below are unweighted stress-distribution results, not operational prevalence or workload.

{table(sim_table, ['bank','arm','no_reuse','overlap_90','solution_reissue','new_information'])}

On the software bank, grouping reduces the no-reuse-to-90%-overlap loss degradation relative to singleton pooling by 0.018405 (grouped-minus-singleton contrast -0.018405, descriptive paired 95% bootstrap interval [-0.030073, -0.007540]). Yet grouped absolute heavy-overlap loss is higher than latest-only. Its degradation is also greater than latest-only (contrast +0.141405). Shared sensor bias changes the conclusion against singleton pooling: grouped-minus-singleton degradation contrast +0.074352, interval [0.045729, 0.102562]. These intervals condition on fixed trained models and independent synthetic scenarios; they exclude training-bank uncertainty and do not correct the many exploratory comparisons.

All arms pass exact-replay invariance. **Fixed-time, thinning, and change-point controls produce the same predictions as singleton pooling in this generator.** Six-hour thinning retains every message at 0.8-day spacing; risk/OD values change each time; the fixed groups do not provide a useful distinct comparison here. This is a limitation of the pilot design and prevents claiming that grouping beats diverse controls.

## New-information control and model failure

The cumulative-information condition uses 10 through 60 unique observations. The fitted classifiers see only fixed windows of 10 observations during training, creating a shift in covariance and observation-count inputs. Their worsening loss is therefore not evidence that new observations are harmful. The correctly specified oracle's state error diagnostic is:

{table(oracle, ['bank','unique_observations','mean_squared_state_error'])}

More observations improve the state estimate in these saved samples, while final-class forecast utility fails to improve reliably. Revise the training regimes and distinct cadence controls in V02 before treating the positive control as passed. Shared-bias calculations use the joint covariance of the mean R/n+B and have a separate full-joint Gaussian test. Independent Cartesian integration agrees with disk quadrature in the numerical validation cases. This validates calculations, not orbital or operational fidelity.

## Decision and falsifiable next step

**NARROW:** develop the benchmark/identification question first: with fixed final labels and a matched latest message, does reuse degrade history-based forecasting, and can a method reduce that degradation while remaining competitive in absolute loss against distinct simple controls? The present pilot supports a reuse effect in one regime, but cannot establish robust superiority. Stop the method-superiority route if corrected controls or plausible bias erase its advantage; a well-supported negative or identifiability finding remains possible.

1. V01: finish the primary-source compatibility table for close weighting/classification, sequence/ensemble and fusion methods. Full methods that remain inaccessible must be labeled discussion-only; novelty remains unresolved.
2. V02: make cadence irregular so thinning and fixed groups differ; test component ablations and oracle observation lineage; include development training matched to new-information conditions; separate well-specified and bias stress claims. Retain this failed/limited pilot rather than replacing it.
3. Use paired scenario variation and training-seed sensitivity to choose a meaningful effect and sample size. Do not pick a primary comparison solely because its exploratory interval excludes zero.
4. V03: freeze one claim, comparator, condition, sample size, inference, failure handling and software before V04. Scientific seed 20261012 and scenario IDs scientific:00000..04999 are reserved but **not generated**. Candidate unseen anisotropic configuration and sample size are not yet a frozen protocol.
5. Keep retrospective real results separate. With 66 independent positives, even zero misses would give a one-sided exact 95% upper miss bound about 4.44%; the observed misses are not zero. Track E still needs new independent outcomes and a valid precision design.

The runs fit on this workstation without a paid inference campaign. Per-fold and per-arm elapsed times are saved in selection JSON files. The available sample sizes and provenance do not justify deployment, collision-prevention, analyst-time, or one-percent-miss claims.

## Continuation and reproducibility

Run `.venv/Scripts/python.exe -m research.summarize_pilot --run-id <new_unique_id>` from the repository to reconstruct this report from the named saved inputs. It never retrains a model or generates reserved scenarios. Use a new run ID; existing directories are protected. Exact run-time source is in each `code_snapshot.zip`, and current source changes must not silently redefine historical runs. All tables are generated from saved predictions/metrics; row counts, fold disjointness, component maxima and checksums are audited. Raw data, 45 historical artifacts and all eight frozen files remain unchanged.

Failed runs `data_20261009_v1` (inefficient correlated SQL) and `cv_20261009_v1` (superseded by equivalent batched transforms) remain explicitly failed and are excluded from scientific summaries. Batched versus separate transforms were tested for exact equality. See `RESEARCH_CHECKLIST.md` for implementation commands, test results and handoff. This report is a feasibility checkpoint, not the final manuscript or an independent reproduction review.
'''
        (run.path / 'pilot_report.md').write_text(report, encoding='utf-8')
        print(report, flush=True)


if __name__ == '__main__':
    main()
