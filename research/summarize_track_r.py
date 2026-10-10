"""Report the frozen Track R scientific run (V04) without changing any decision.

Verifies the run's artifacts and phase-2 commit, reconstructs every frozen result
in `analysis.json` from the saved labelled predictions with the frozen functions
and seeds, and adds the protocol's "reported regardless" descriptive tables. A
post-hoc coverage check on the observed scientific variance components is
labelled as such and plays no part in the decisions.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json
from research.bank_interval_validation import components_from, validate
from research.metrics import class_metrics
from research.summarize_pilot import audit_run, table
from research.summarize_real import recalibration
from research.track_r_analysis import (bank_combined_interval, combined_one_sided_p, holm, primary_decision,
                                       reuse_miss_summary)
from research.track_r_scientific import bank_matrix

POST_HOC_REPLICATES = 400


def reconstruct(labelled: pd.DataFrame, protocol: dict) -> dict:
    """Recompute analysis.json exactly as phase 3 did."""
    analysis, results = protocol['analysis'], {}
    for spec in analysis['contrasts']:
        matrix, misses = bank_matrix(labelled, spec['arm'], spec['comparator'], spec['condition'], spec['estimand'])
        interval = bank_combined_interval(matrix, analysis['bootstrap_resamples'], analysis['bootstrap_seed'])
        record = {k: v for k, v in interval.items() if k != 't_star'}
        record.update(spec)
        if spec.get('null') is not None:
            record['p_value'] = combined_one_sided_p(interval, spec['null'], spec['alternative'])
        if spec['id'] == analysis['primary']:
            record['decision'] = primary_decision(interval, analysis['margin'])
        if spec['estimand'] == 'degradation':
            pooled = misses[['reuse_new_misses_arm', 'reuse_recovered_misses_arm', 'positives']].sum()
            record['reuse_misses_pooled_over_banks'] = reuse_miss_summary(int(pooled.reuse_new_misses_arm),
                                                                          int(pooled.reuse_recovered_misses_arm), int(pooled.positives))
        results[spec['id']] = record
    rejected = holm({k: results[k]['p_value'] for k in analysis['confirmatory_secondary']}, analysis['alpha'])
    for k, v in rejected.items():
        results[k]['holm_rejected'] = v
    return results


def same(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return (a is None and b is None) or (a is not None and b is not None and (a == b or (math.isnan(a) and math.isnan(b))))
    return a == b


def descriptive(labelled: pd.DataFrame) -> dict[str, pd.DataFrame]:
    losses, calibration, per_bank = [], [], []
    for (arm, condition), g in labelled.groupby(['arm', 'condition'], sort=True):
        m = class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())
        losses.append({'arm': arm, 'condition': condition, 'rows': len(g), 'banks': g.training_bank.nunique(),
                       'mean_log_loss': m['log_loss'], 'brier': m['brier'], 'roc_auc': m['roc_auc'],
                       'mean_review_fraction': m['review_fraction'], 'miss_rate': m['miss_rate']})
        calibration.append({'arm': arm, 'condition': condition, **recalibration(g.y.to_numpy(), g.q.to_numpy())})
    for (bank, arm, condition), g in labelled.groupby(['training_bank', 'arm', 'condition'], sort=True):
        per_bank.append({'training_bank': bank, 'arm': arm, 'condition': condition, 'log_loss': float(g.log_loss.mean()),
                         'reviewed': int(g.review95.sum()), 'missed': int(((g.y == 1) & ~g.review95).sum()), 'positives': int(g.y.sum())})
    return {'losses.csv': pd.DataFrame(losses), 'calibration.csv': pd.DataFrame(calibration), 'per_bank_losses.csv': pd.DataFrame(per_bank)}


def bank_contrast_table(labelled: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    rows = []
    for spec in protocol['analysis']['contrasts']:
        matrix, misses = bank_matrix(labelled, spec['arm'], spec['comparator'], spec['condition'], spec['estimand'])
        for k, bank in enumerate(sorted(labelled.training_bank.unique())):
            rows.append({'id': spec['id'], 'training_bank': bank, 'mean': float(matrix[:, k].mean()),
                         **misses[misses.training_bank == bank].drop(columns='training_bank').iloc[0].to_dict()})
    return pd.DataFrame(rows)


def build(source: Path, protocol: dict, post_hoc_seed: int, run_id: str):
    """Verify, reconstruct and tabulate one completed scientific run; returns tables, audit and report text."""
    commit = json.loads((source / 'phase2_commit.json').read_text(encoding='utf-8'))
    if sha256(source / 'predictions_unlabeled.parquet') != commit['predictions_sha256']:
        raise ValueError('Unlabelled predictions changed after the phase-2 commit')
    labelled = read_table(source / 'predictions_labelled.parquet')
    recorded = json.loads((source / 'analysis.json').read_text(encoding='utf-8'))
    if not same(json.loads(json.dumps(reconstruct(labelled, protocol))), recorded):
        raise ValueError('analysis.json does not reconstruct from the labelled predictions')
    tables = descriptive(labelled)
    tables['bank_contrasts.csv'] = bank_contrast_table(labelled, protocol)
    tables['decisions.csv'] = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, dict)} for r in recorded.values()])
    files = sorted(source.glob('selection_*.json'))
    selections = [json.loads(f.read_text(encoding='utf-8')) for f in files]
    tables['selections.csv'] = pd.DataFrame([{'file': f.name, 'arm': s['arm'], 'C': s['C'], 'at_upper_C': s['C'] == max(protocol['C']),
                                              'maximum_iterations': s.get('maximum_observed_iterations', s.get('maximum_iterations'))}
                                             for f, s in zip(files, selections)])
    matrix, _ = bank_matrix(labelled, 'singleton', 'latest_metadata', 'overlap_90', 'degradation')
    parts = components_from(matrix)
    post = pd.DataFrame(validate(parts, matrix.shape[1], matrix.shape[0], POST_HOC_REPLICATES, np.random.default_rng(post_hoc_seed)))
    tables['post_hoc_coverage.csv'] = post.assign(id='P1', note='post hoc; simulated from observed scientific components')
    integration = json.loads((source / 'integration.json').read_text(encoding='utf-8'))
    text = report(recorded, tables, protocol, parts, run_id, source.name, integration)
    audit = {'phase2_commit_verified': True, 'analysis_reconstructed_exactly': True, 'labelled_rows': len(labelled),
             'scientific_components_P1': {k: v for k, v in parts.items() if k not in ('scenario_effects', 'residuals')},
             'independent_pre_run_check': 'waived by the user for V04 (see track_r_authorization.json)'}
    return tables, audit, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('docs/research/execution/track_r_protocol.json'))
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--post-hoc-seed', type=int, default=20261111)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    source = args.source.resolve()
    source_audit = audit_run(source)
    protocol = json.loads(args.protocol.read_text(encoding='utf-8'))
    with Run(args.run_id, 'track_r_scientific_report', {'source': str(source)}, [source / 'manifest.json', args.protocol]) as run:
        tables, audit, report_text = build(source, protocol, args.post_hoc_seed, args.run_id)
        for name, frame in tables.items():
            frame.to_csv(run.path / name, index=False)
        write_json(run.path / 'audit.json', {'source_run': source_audit, **audit})
        (run.path / 'report.md').write_text(report_text, encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('audit.json', *sorted(tables), 'report.md')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name], 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


def report(recorded, tables, protocol, parts, run_id, source, integration) -> str:
    p1 = recorded['P1']
    family = protocol['analysis']['confirmatory_secondary']
    secondary = tables['decisions.csv'][tables['decisions.csv'].id.isin(family)][['id', 'arm', 'comparator', 'condition', 'estimand', 'null', 'mean', 'lower', 'upper', 'p_value', 'holm_rejected']]
    exploratory = [c['id'] for c in protocol['analysis']['contrasts'] if c.get('role') == 'exploratory' or c.get('null') is None]
    explore = tables['decisions.csv'][tables['decisions.csv'].id.isin(exploratory)][['id', 'arm', 'comparator', 'condition', 'estimand', 'mean', 'lower', 'upper', 'scenario_lower', 'scenario_upper']]
    misses = p1['reuse_misses_pooled_over_banks']
    losses = tables['losses.csv']
    focus = losses[losses.condition.isin(['no_reuse', 'overlap_90', 'solution_reissue', 'new_information'])]
    return f'''# Track R scientific evaluation (V04)

Run `{source}`, reported by `{run_id}`. **Confirmatory evaluation under the frozen
protocol** ([protocol](../../execution/track_r_protocol.json), canonical SHA-256
`{protocol_hash_text(protocol)}`), in the held-out simulator configuration (noise variance ratio 4
rotated 30 degrees). There are {protocol['independent_training_banks']} independent training banks of
{protocol['training_scenarios']:,} scenarios and {protocol['evaluation_scenarios']:,} evaluation scenarios.
This is a controlled static encounter-plane simulation: not orbital validation,
not operational evidence, and never pooled with the retrospective real-data (A01)
results. The user authorized the run, and the pre-run independent analysis check
was waived ([authorization](../../execution/track_r_authorization.json)).

Integrity checks:
- the unlabelled predictions match their phase-2 commit hash;
- every result in `analysis.json` reconstructs exactly from the labelled
  predictions, using the frozen functions and seeds.

## Primary result (P1)

**Decision: {p1['decision'].replace('_', ' ')}.**

| Quantity | Value |
|---|---|
| Estimate (mean over {p1['banks']} banks x {p1['n']:,} scenarios) | {p1['mean']:.6f} |
| Bank-combined 95% interval (frozen) | [{p1['lower']:.6f}, {p1['upper']:.6f}] |
| Margin | {protocol['analysis']['margin']} |
| Scenario-only bootstrap-t interval (conditional on these fits; sensitivity) | [{p1['scenario_lower']:.6f}, {p1['scenario_upper']:.6f}] |
| Student t interval (scenario component; sensitivity) | [{p1['t_lower']:.6f}, {p1['t_upper']:.6f}] |
| Bank SE / scenario SE | {p1['bank_se']:.6f} / {p1['se']:.6f} |
| One-sided p (H0: P1 <= {protocol['analysis']['margin']}) | {p1['p_value']:.6g} |

The rule was: confirm if the lower bound exceeds the margin, not material if the
upper bound falls below it, otherwise inconclusive.

## Confirmatory secondary family (Holm, one-sided familywise 0.05)

{table(secondary, list(secondary.columns))}

## Exploratory

{table(explore, list(explore.columns))}

Reuse-induced misses for the history arm (positives missed under 90% overlap but
reviewed without reuse), pooled over banks: {misses['new_misses']} new and
{misses['recovered_misses']} recovered among {misses['positives']:,} positive
bank-scenario pairs. The new-miss rate is {misses['new_miss_rate']:.4f}, with an
exact 95% interval of [{misses['new_miss_rate_lower95']:.4f}, {misses['new_miss_rate_upper95']:.4f}] and an
exact McNemar p of {misses['exact_mcnemar_p']:.3g}. Banks share scenarios, so the pooled count
is descriptive.

## Prespecified diagnostics

- **Integration check** (label-free) on the scientific noise covariance: worst
  relative difference {integration['max_rel_difference']:.2e}.
- **Grid-edge selections** (C = {max(protocol['C']):g}; a search limit, not a failure):
  {int(tables['selections.csv'].at_upper_C.sum())} of {len(tables['selections.csv'])} models.
  The largest observed iteration count was {int(tables['selections.csv'].maximum_iterations.max())} against a cap of
  {protocol['max_iter']:,}.

## Absolute losses (mean over banks and scenarios)

The enriched stress population is unweighted; review fractions are not
operational workload.

{table(focus, list(focus.columns))}

Full per-arm, per-condition and per-bank tables, calibration and per-bank
contrasts are in the bundle.

## Post-hoc coverage check (not part of the decision)

Designs simulated from the observed scientific P1 components (bank SD
{parts['bank_sd']:.6f}, scenario variance {parts['var_scenario']:.6f}) with {POST_HOC_REPLICATES} replicates:

{table(tables['post_hoc_coverage.csv'], ['method', 'banks', 'scenarios', 'replicates', 'false_low_side', 'false_high_side', 'coverage', 'median_half_width'])}

## Limits

- **Simulator:** static two-dimensional encounter-plane model with a synthetic
  label (final reported-risk class), not collision occurrence.
- **Implementations:** bounded logistic implementations, a declared C grid and
  selected-OOF calibration reuse; no risk certification.
- **Review:** the independent pre-run check was waived; the A03 independent
  review is still required.
'''


def protocol_hash_text(protocol) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(protocol, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


if __name__ == '__main__':
    main()
