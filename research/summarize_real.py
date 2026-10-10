"""A01 retrospective real-CDM analysis of the frozen-choice refit (exposed evidence).

Metrics, calibration, workload/miss frontiers, paired event-level contrasts with
studentized and mission-cluster intervals, leave-one-mission-out sensitivity,
censoring diagnostics and a failure listing. Training-cohort OOF and the exposed
historical test split are reported separately and never pooled with simulation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

from research.artifacts import RUN_ROOT, Run, read_table, sha256, write_json
from research.metrics import class_metrics, loss
from research.summarize_pilot import audit_run, table
from research.track_r_analysis import studentized_bootstrap

FLOOR = -30.0
RECALLS = ('90', '95', '99')


def recalibration(y, q) -> dict:
    """Unpenalized logistic recalibration of y on logit(q): intercept and slope."""
    x = logit(np.clip(np.asarray(q, float), 1e-6, 1 - 1e-6))
    y = np.asarray(y, float)

    def objective(v):
        z = v[0] + v[1] * x
        r = expit(z) - y
        return np.mean(np.logaddexp(0, z) - y * z), np.array([r.mean(), (r * x).mean()])
    fit = minimize(objective, [0., 1.], jac=True, method='BFGS', options={'gtol': 1e-10, 'maxiter': 1000})
    # BFGS can stop on precision loss after reaching the optimum; accept only a near-zero gradient.
    if not (fit.success or np.max(np.abs(fit.jac)) < 1e-8):
        raise RuntimeError('Recalibration did not converge')
    return {'calibration_intercept': float(fit.x[0]), 'calibration_slope': float(fit.x[1]),
            'mean_q_minus_observed': float(np.mean(q) - y.mean())}


def reliability(y, q, bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({'y': y, 'q': q})
    frame['bin'] = pd.qcut(frame.q.rank(method='first'), bins, labels=False)
    return frame.groupby('bin').agg(n=('y', 'size'), positives=('y', 'sum'), mean_q=('q', 'mean'),
                                     observed=('y', 'mean')).reset_index()


def frontier(y, q, points: int = 101) -> pd.DataFrame:
    """Review fraction and missed positives across score quantile thresholds (descriptive)."""
    y, q = np.asarray(y), np.asarray(q)
    thresholds = np.unique(np.r_[0., np.quantile(q, np.linspace(0, 1, points))])
    rows = [{'threshold': float(t), 'reviewed': int((q >= t).sum()), 'review_fraction': float((q >= t).mean()),
             'missed': int(((q < t) & (y == 1)).sum())} for t in thresholds]
    return pd.DataFrame(rows)


def cluster_bootstrap_t(values, clusters, resamples: int, seed: int, alpha: float = .05) -> dict:
    """Mission-cluster bootstrap-t for a pooled event mean with cluster-robust standard errors."""
    v, g = np.asarray(values, float), np.asarray(clusters)
    labels = np.unique(g)
    if len(labels) < 3:
        raise ValueError('Need at least three clusters')
    totals = np.array([v[g == c].sum() for c in labels])
    counts = np.array([(g == c).sum() for c in labels])

    def mean_se(t, n):
        m = t.sum() / n.sum()
        dev = t - m * n
        k = len(t)
        return m, math.sqrt(k / (k - 1) * np.sum(dev ** 2)) / n.sum()
    mean, se = mean_se(totals, counts)
    rng = np.random.default_rng(seed)
    t_star = []
    for _ in range(resamples):
        pick = rng.integers(0, len(labels), size=len(labels))
        m, s = mean_se(totals[pick], counts[pick])
        if s > 0:
            t_star.append((m - mean) / s)
    t_star = np.asarray(t_star)
    upper_q, lower_q = np.quantile(t_star, [1 - alpha / 2, alpha / 2])
    return {'mean': float(mean), 'cluster_se': float(se), 'lower': float(mean - upper_q * se), 'upper': float(mean - lower_q * se),
            'clusters': int(len(labels)), 'valid_resamples': int(len(t_star))}


def paired(frame: pd.DataFrame, arm: str, comparator: str) -> pd.DataFrame:
    a = frame[frame.arm == arm].set_index('series_id')
    b = frame[frame.arm == comparator].set_index('series_id')
    if not a.index.sort_values().equals(b.index.sort_values()):
        raise ValueError('Arms must share events')
    b = b.reindex(a.index)
    if not (a.y == b.y).all():
        raise ValueError('Paired label mismatch')
    return pd.DataFrame({'difference': loss(a.y.to_numpy(), a.q.to_numpy()) - loss(b.y.to_numpy(), b.q.to_numpy()),
                         'mission_id': a.mission_id, 'final_risk': a.final_risk, 'y': a.y}, index=a.index)


def contrast_rows(frame, split, contrasts, resamples, seed):
    rows, lomo = [], []
    for spec in contrasts:
        if spec['arm'] not in set(frame.arm) or spec['comparator'] not in set(frame.arm):
            continue
        d = paired(frame, spec['arm'], spec['comparator'])
        boot = studentized_bootstrap(d.difference.to_numpy(), resamples, seed)
        cluster = cluster_bootstrap_t(d.difference.to_numpy(), d.mission_id.to_numpy(), resamples, seed + 1)
        above = d[d.final_risk > FLOOR]
        above_boot = studentized_bootstrap(above.difference.to_numpy(), resamples, seed + 2)
        rows.append({'split': split, 'id': spec['id'], 'arm': spec['arm'], 'comparator': spec['comparator'], 'events': len(d),
                     'positives': int(d.y.sum()), 'mean': boot['mean'], 'event_lower': boot['lower'], 'event_upper': boot['upper'],
                     't_lower': boot['t_lower'], 't_upper': boot['t_upper'], 'mission_lower': cluster['lower'],
                     'mission_upper': cluster['upper'], 'missions': cluster['clusters'],
                     'above_floor_events': len(above), 'above_floor_mean': above_boot['mean'],
                     'above_floor_lower': above_boot['lower'], 'above_floor_upper': above_boot['upper']})
        for mission in sorted(d.mission_id.unique()):
            rest = d[d.mission_id != mission]
            lomo.append({'split': split, 'id': spec['id'], 'left_out_mission': mission,
                         'left_out_events': int((d.mission_id == mission).sum()),
                         'left_out_positives': int(d.y[d.mission_id == mission].sum()), 'mean_without': float(rest.difference.mean())})
    return pd.DataFrame(rows), pd.DataFrame(lomo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    source = args.source.resolve()
    source_audit = audit_run(source)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    contract = manifest['config']
    data, reference = RUN_ROOT / contract['data_run'], RUN_ROOT / contract['reference_run']
    with Run(args.run_id, 'real_retrospective_summary', {'source': str(source)}, [source / 'manifest.json', reference / 'manifest.json']) as run:
        missions = {s: read_table(data / f'causal_features_{s}.parquet')[['series_id', 'mission_id', 'latest_risk']] for s in ('train', 'test')}
        oof = read_table(source / 'oof_predictions.parquet').merge(missions['train'], on='series_id', validate='many_to_one')
        gbm = read_table(reference / 'predictions.parquet')
        gbm = gbm[gbm.arm == 'causal_gbm'].merge(missions['train'], on='series_id', validate='one_to_one')
        oof = pd.concat([oof, gbm[oof.columns.intersection(gbm.columns)]], ignore_index=True)
        test = read_table(source / 'test_predictions.parquet').merge(missions['test'], on='series_id', validate='many_to_one')
        frames = {'training_oof': oof, 'historical_test': test}
        metrics, calibration, bins, frontiers, failures = [], [], [], [], []
        for split, frame in frames.items():
            for arm, g in frame.groupby('arm', sort=True):
                base = class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review_95.to_numpy())
                row = {'split': split, 'arm': arm, **{k: base[k] for k in ('n', 'positives', 'log_loss', 'brier', 'roc_auc', 'average_precision')}}
                for r in RECALLS:
                    m = class_metrics(g.y.to_numpy(), g.q.to_numpy(), g[f'review_{r}'].to_numpy())
                    row[f'reviewed_{r}'], row[f'missed_{r}'] = m['reviewed'], m['fn']
                metrics.append(row)
                calibration.append({'split': split, 'arm': arm, **recalibration(g.y.to_numpy(), g.q.to_numpy())})
                bins.append(reliability(g.y.to_numpy(), g.q.to_numpy()).assign(split=split, arm=arm))
                frontiers.append(frontier(g.y.to_numpy(), g.q.to_numpy()).assign(split=split, arm=arm))
                missed = g[(g.y == 1) & ~g.review_95]
                failures.extend({'split': split, 'arm': arm, 'series_id': r.series_id, 'mission_id': r.mission_id,
                                 'latest_risk': r.latest_risk, 'final_risk': r.final_risk, 'q': r.q, 'threshold_95': r.threshold_95}
                                for r in missed.itertuples(index=False))
        analyses = contract['analyses']
        contrasts, lomo = [], []
        for split, frame in frames.items():
            c, l = contrast_rows(frame, split, analyses['paired_contrasts'], 9999, 20261109)
            contrasts.append(c)
            lomo.append(l)
        contrasts, lomo = pd.concat(contrasts, ignore_index=True), pd.concat(lomo, ignore_index=True)
        censoring = (oof[oof.arm == 'latest'].assign(at_floor=lambda d: d.final_risk <= FLOOR)
                     .groupby('mission_id').agg(events=('y', 'size'), positives=('y', 'sum'), at_floor=('at_floor', 'sum')).reset_index())
        reproduction = pd.DataFrame(json.loads((source / 'reference_reproduction.json').read_text(encoding='utf-8')))
        selections = pd.DataFrame(json.loads((source / 'selections.json').read_text(encoding='utf-8')))
        out = run.path
        named = {'metrics.csv': pd.DataFrame(metrics), 'calibration.csv': pd.DataFrame(calibration),
                 'reliability.csv': pd.concat(bins, ignore_index=True), 'frontiers.csv': pd.concat(frontiers, ignore_index=True),
                 'contrasts.csv': contrasts, 'leave_one_mission_out.csv': lomo, 'censoring.csv': censoring,
                 'missed_positives.csv': pd.DataFrame(failures), 'reference_reproduction.csv': reproduction,
                 'selections.csv': selections[['arm', 'fold', 'C', 'calibration_slope', 'calibration_intercept', 'maximum_iterations']]}
        for name, frame in named.items():
            frame.to_csv(out / name, index=False)
        write_json(out / 'audit.json', {'source_run': source_audit, 'training_events': int((oof.arm == 'latest').sum()),
                   'test_events': int((test.arm == 'latest').sum()), 'evidence': contract['evidence_type'],
                   'reproduced_reference_folds': int(reproduction.identical_predictions.sum()), 'reference_folds': len(reproduction),
                   'scope': 'Exposed retrospective analysis; not confirmation and not pooled with simulation.'})
        (out / 'report.md').write_text(report(named, contract, args.run_id, source.name), encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('audit.json', *sorted(named), 'report.md')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name, reference.name], 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


def report(named, contract, run_id, source) -> str:
    metrics, calibration, contrasts = named['metrics.csv'], named['calibration.csv'], named['contrasts.csv']
    lomo, censoring, missed = named['leave_one_mission_out.csv'], named['censoring.csv'], named['missed_positives.csv']
    reproduction = named['reference_reproduction.csv']
    lomo_range = (lomo.groupby(['split', 'id']).agg(missions=('left_out_mission', 'size'), mean_without_min=('mean_without', 'min'),
                                                    mean_without_max=('mean_without', 'max')).reset_index())
    floor_share = censoring.at_floor.sum() / censoring.events.sum()
    missed_counts = missed.groupby(['split', 'arm']).size().rename('missed_at_95').reset_index()
    changed = reproduction[~reproduction.identical_predictions]
    return f'''# A01 retrospective real-CDM analysis

Run `{run_id}` from refit `{source}`. **Exposed retrospective evidence** on the Kelvins
benchmark cohort under the frozen Track R analysis choices ([contract](../../execution/a01_contract.json)).
It is not confirmation, it is not pooled with simulation, and it is not an
operational workload or safety estimate. The label is final recorded log-risk
>= -6, not collision occurrence.

## Inputs

- **Training cohort:** 8,293 events / 66 positives, out-of-fold over the stored 5x3
  nested whole-event folds.
- **Historical test split:** 2,167 / 150, evaluated once with final models selected
  on the full training cohort. Its labels were already exposed but were never used
  for a model choice here.
- **Arms:** `latest`, `latest_metadata`, `singleton` and `grouped`, refitted with the
  frozen six-value C grid and strict convergence. `causal_gbm` OOF predictions are
  reused unchanged as an external reference.
- **Reproduction:** {int(reproduction.identical_predictions.sum())}/{len(reproduction)} arm-folds reproduce
  the earlier narrower-grid run's predictions exactly. Changed folds:
  {', '.join(f"{r.arm} fold {r.fold} (C {r.previous_C:g} to {r.C:g})" for r in changed.itertuples()) or 'none'}.

## Label shift between the two exposed sets

The training cohort's positive share is {metrics[metrics.split == 'training_oof'].positives.iloc[0] / metrics[metrics.split == 'training_oof'].n.iloc[0]:.2%};
the historical test split's is {metrics[metrics.split == 'historical_test'].positives.iloc[0] / metrics[metrics.split == 'historical_test'].n.iloc[0]:.2%}.
Probabilities calibrated on the training cohort therefore under-predict on the
test split; see the calibration intercepts. Ranking metrics and paired contrasts
are less affected than calibration-in-the-large.

## Discrimination, loss and nominal operating points

Review and miss counts use training-only thresholds at nominal 90/95/99% recall.
They are not population guarantees.

{table(metrics, list(metrics.columns))}

## Calibration

Logistic recalibration of outcomes on logit(q): an intercept of 0 and slope of 1
mean calibrated. Decile reliability bins are in `reliability.csv`.

{table(calibration, list(calibration.columns))}

## Paired event-level contrasts (negative favours the first arm)

Differences are in clipped log loss per event. Intervals:
- `event`: studentized bootstrap over events (B = 9,999);
- `t`: Student t;
- `mission`: mission-cluster bootstrap-t, which allows within-mission dependence;
- `above_floor`: repeated on events whose final log-risk is above the -30 floor.

{table(contrasts, ['split', 'id', 'arm', 'comparator', 'events', 'positives', 'mean', 'event_lower', 'event_upper', 'mission_lower', 'mission_upper', 'missions', 'above_floor_events', 'above_floor_mean', 'above_floor_lower', 'above_floor_upper'])}

Leave-one-mission-out range of each contrast's mean:

{table(lomo_range, list(lomo_range.columns))}

## Censoring

{floor_share:.1%} of training events have final log-risk at the -30 floor, which is
treated as censored. The binary label is unaffected because -30 lies far below
the -6 threshold, but these events dominate the loss averages. Every positive
lies above the floor. Floor share by mission:

{table(censoring, list(censoring.columns))}

## Missed positives at the nominal 95% training-recall threshold

{table(missed_counts, list(missed_counts.columns))}

`missed_positives.csv` lists each missed event with its mission, latest risk,
final risk and q.

## Limits

- Exposed data: the training cohort shaped every development choice, and the
  historical test labels have long been public.
- Retrospective cohort selection uses future records (eligibility); see Report 1.
- Missions are few and unbalanced (19 in training). The mission-cluster interval
  has few clusters and treats missions as exchangeable.
- Public CDMs carry no observation lineage, so the simulation's reuse contrasts
  (P1) cannot be measured here. R1/R2 are absolute comparisons only.
'''


if __name__ == '__main__':
    main()
