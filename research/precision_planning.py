"""Scenario-paired precision planning from audited development predictions.

Reads exposed development predictions only; fits nothing and generates no
scenario. Rows are training-trial x bank x condition x arm pairs, but the
independent unit is the evaluation scenario (1,000 per exposed bank), and the
three 800-scenario training subsets overlap the full-reference cohort.
Resampling checks use the development per-scenario differences as a plausible
distribution; they are planning approximations, not scientific inference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from scipy import stats

from research.artifacts import RUN_ROOT, Run, read_table, sha256, write_json
from research.summarize_pilot import audit_run, table

SOURCES = ('tuning_20261009_v1', 'covariance_20261009_v1', 'sequence_20261010_v1', 'components_20261010_v1')
EXPORTS = {'covariance_20261009_v1': 'covariance_2026-10-09', 'sequence_20261010_v1': 'sequence_2026-10-10',
           'components_20261010_v1': 'components_2026-10-10'}
REGIME = 'matched_mixture'
REFERENCE_SEED = 20261022
COMPARATORS = ('latest_metadata', 'singleton')
CONDITIONS = ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue', 'new_information')
CANDIDATES = (
    {'id': 'P1', 'role': 'primary_candidate', 'estimand': 'degradation', 'arm': 'singleton', 'comparator': 'latest_metadata',
     'condition': 'overlap_90', 'bank': 'software'},
    {'id': 'S1', 'role': 'secondary_candidate', 'estimand': 'absolute', 'arm': 'singleton', 'comparator': 'latest_metadata',
     'condition': 'overlap_90', 'bank': 'software'},
    {'id': 'S2', 'role': 'secondary_candidate', 'estimand': 'degradation', 'arm': 'grouped', 'comparator': 'singleton',
     'condition': 'overlap_90', 'bank': 'software'},
    {'id': 'S3', 'role': 'secondary_candidate', 'estimand': 'degradation', 'arm': 'oracle_lineage_weight', 'comparator': 'singleton',
     'condition': 'overlap_90', 'bank': 'software'},
    {'id': 'S4', 'role': 'secondary_candidate', 'estimand': 'degradation', 'arm': 'singleton', 'comparator': 'latest_metadata',
     'condition': 'overlap_90', 'bank': 'bias_stress'},
    {'id': 'S5', 'role': 'secondary_candidate', 'estimand': 'degradation', 'arm': 'singleton', 'comparator': 'latest_metadata',
     'condition': 'solution_reissue', 'bank': 'software'},
    {'id': 'S6', 'role': 'secondary_candidate', 'estimand': 'absolute', 'arm': 'singleton', 'comparator': 'latest_metadata',
     'condition': 'solution_reissue', 'bank': 'software'},
)
HALF_WIDTHS = (0.005, 0.01, 0.02)
MARGINS = (0.0, 0.01, 0.02)
N_GRID = (500, 1000, 2000, 3000, 5000)
RESAMPLES = 4000
MISS_MARGINS = (0.01, 0.02, 0.05)
ALPHA = 0.05
POWER = 0.9


def paired_frames(predictions: pd.DataFrame) -> dict:
    """Per-scenario log loss, review and miss pivots for one trial/regime/bank."""
    y = predictions.groupby('series_id').y
    if (y.nunique() != 1).any():
        raise ValueError('Paired label mismatch')
    frame = predictions.assign(reviewed=predictions.review95.astype(bool))
    pivots = {m: frame.pivot(index='series_id', columns=['arm', 'condition'], values=m) for m in ('log_loss', 'reviewed')}
    if any(p.isna().any().any() for p in pivots.values()):
        raise ValueError('Incomplete paired cases')
    return {'y': y.first().astype(int), **pivots}


def contrast(pivots: dict, arm: str, comparator: str, condition: str, estimand: str) -> pd.Series:
    """Per-scenario clipped log-loss contrast, as in every V02 summary export."""
    loss = pivots['log_loss']
    absolute = loss[arm, condition] - loss[comparator, condition]
    if estimand == 'absolute':
        return absolute
    if estimand == 'degradation':
        return absolute - (loss[arm, 'no_reuse'] - loss[comparator, 'no_reuse'])
    raise ValueError(estimand)


def discordance(pivots: dict, arm: str, comparator: str, condition: str) -> dict:
    """Review discordance over all scenarios; miss discordance over positives only."""
    review, y = pivots['reviewed'], pivots['y'].to_numpy() == 1
    m, b = review[arm, condition].to_numpy(), review[comparator, condition].to_numpy()
    m0 = review[arm, 'no_reuse'].to_numpy()
    return {'review_arm_only': int((m & ~b).sum()), 'review_comparator_only': int((b & ~m).sum()),
            'new_misses': int((y & ~m & b).sum()), 'recovered_misses': int((y & m & ~b).sum()),
            'shared_misses': int((y & ~m & ~b).sum()),
            'reuse_new_misses_arm': int((y & ~m & m0).sum()), 'reuse_recovered_misses_arm': int((y & m & ~m0).sum())}


def describe(values: pd.Series) -> dict:
    x = values.to_numpy(dtype=float)
    if len(x) < 2 or not np.isfinite(x).all():
        raise ValueError('Expected finite paired differences')
    sd = float(x.std(ddof=1))
    return {'scenarios': len(x), 'mean': float(x.mean()), 'sd': sd, 'se': sd / math.sqrt(len(x)),
            'q01': float(np.quantile(x, .01)), 'q99': float(np.quantile(x, .99)),
            'exact_zero_fraction': float(np.mean(np.abs(x) < 1e-12)), 'skewness': float(stats.skew(x)) if sd > 0 else 0.0}


def n_for_half_width(sd: float, half_width: float, alpha: float = ALPHA) -> int:
    """Normal-approximation scenarios for a two-sided interval half-width."""
    return math.ceil((stats.norm.ppf(1 - alpha / 2) * sd / half_width) ** 2)


def n_for_margin(sd: float, true_effect: float, margin: float, alpha: float = ALPHA, power: float = POWER) -> float:
    """Scenarios for P(lower two-sided bound > margin) = power; infinite if effect <= margin."""
    if true_effect <= margin:
        return math.inf
    return math.ceil(((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) * sd / (true_effect - margin)) ** 2)


def resample_moments(values: np.ndarray, n: int, rng: np.random.Generator, resamples: int = RESAMPLES,
                     chunk: int = 250) -> tuple[np.ndarray, np.ndarray]:
    """Means and standard errors of n scenarios drawn with replacement from values."""
    x = np.asarray(values, dtype=float)
    means, ses = [], []
    for start in range(0, resamples, chunk):
        draw = x[rng.integers(0, len(x), size=(min(chunk, resamples - start), n))]
        means.append(draw.mean(axis=1))
        ses.append(draw.std(axis=1, ddof=1) / math.sqrt(n))
    return np.concatenate(means), np.concatenate(ses)


def interval_properties(means: np.ndarray, ses: np.ndarray, n: int, truth: float, margin: float,
                        alpha: float = ALPHA) -> dict:
    """Two-sided t-interval coverage and margin decisions for resampled moments.

    A location shift of the sampled distribution shifts every mean and the truth
    equally and leaves standard errors unchanged, so callers shift both.
    """
    half = stats.t.ppf(1 - alpha / 2, n - 1) * ses
    lower, upper = means - half, means + half
    return {'n': n, 'true_mean': truth, 'margin': margin, 'resamples': len(means),
            'coverage': float(np.mean((lower <= truth) & (truth <= upper))),
            'lower_above_margin': float(np.mean(lower > margin)), 'upper_below_margin': float(np.mean(upper < margin)),
            'half_width_median': float(np.median(half)), 'half_width_p95': float(np.quantile(half, .95))}


def clopper_pearson_upper(failures: int, trials: int, alpha: float = ALPHA) -> float:
    """One-sided (1 - alpha) exact upper bound, as in Report 2 section 7.2."""
    if trials <= 0:
        raise ValueError('Upper bound needs at least one positive case')
    if failures >= trials:
        return 1.0
    return float(stats.beta.ppf(1 - alpha, failures + 1, trials - failures))


def miss_bound_power(rate: float, positives: int, margin: float, rng: np.random.Generator, resamples: int = RESAMPLES) -> float:
    """P(Clopper-Pearson upper bound on the new-miss rate <= margin) under Binomial(positives, rate)."""
    failures = rng.binomial(positives, rate, size=resamples)
    passing = np.array([clopper_pearson_upper(k, positives) <= margin for k in range(positives + 1)])
    return float(passing[failures].mean())


def load_predictions(runs: dict[str, Path]) -> pd.DataFrame:
    frames = [read_table(path / 'predictions.parquet') for path in runs.values()]
    predictions = pd.concat(frames, ignore_index=True)
    key = ['seed', 'regime', 'bank', 'arm', 'condition', 'series_id']
    if predictions.duplicated(key).any():
        raise ValueError('Duplicate prediction rows across source runs')
    return predictions[predictions.regime == REGIME]


def case_identity(ids) -> dict:
    """Name the exact scenario set behind a row without copying every identifier."""
    ordered = sorted(map(str, ids))
    return {'case_ids_first': ordered[0], 'case_ids_last': ordered[-1],
            'case_ids_sha256': hashlib.sha256('\n'.join(ordered).encode('utf-8')).hexdigest()}


def planning_table(predictions: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows, cache = [], {}
    for (seed, bank), group in predictions.groupby(['seed', 'bank']):
        pivots = paired_frames(group)
        cache[(seed, bank)] = pivots
        identity = case_identity(pivots['y'].index)
        arms = sorted(group.arm.unique())
        for comparator in COMPARATORS:
            for arm in arms:
                if arm == comparator:
                    continue
                for condition in CONDITIONS:
                    for estimand in ('absolute', 'degradation'):
                        rows.append({'seed': seed, 'regime': REGIME, 'bank': bank, 'arm': arm, 'comparator': comparator,
                                     'condition': condition, 'estimand': estimand, 'positives': int(pivots['y'].sum()), **identity,
                                     **describe(contrast(pivots, arm, comparator, condition, estimand)),
                                     **discordance(pivots, arm, comparator, condition)})
    return pd.DataFrame(rows), cache


def reconcile(table_rows: pd.DataFrame, bundles: Path) -> pd.DataFrame:
    """Compare mean/SD and miss differences with every overlapping committed export row."""
    out = []
    for run_id, bundle in EXPORTS.items():
        exported = pd.read_csv(bundles / bundle / 'paired_contrasts.csv')
        exported = exported[exported.regime == REGIME]
        # The covariance export predates per-metric prefixes; its columns are log loss.
        prefix = 'log_loss_' if 'log_loss_absolute_difference' in exported else ''
        for estimand in ('absolute', 'degradation'):
            mine = table_rows[table_rows.estimand == estimand].drop(columns=['regime', 'positives'])
            merged = mine.merge(exported, on=['seed', 'bank', 'arm', 'comparator', 'condition'], validate='one_to_one')
            if merged.empty:
                continue
            miss = math.nan
            if estimand == 'absolute' and 'missed_absolute_difference' in merged:
                own = (merged.new_misses - merged.recovered_misses) / merged.positives
                miss = float((own - merged.missed_absolute_difference).abs().max())
            out.append({'bundle': bundle, 'estimand': estimand, 'rows': len(merged),
                        'max_mean_difference': float((merged['mean'] - merged[f'{prefix}{estimand}_difference']).abs().max()),
                        'max_sd_difference': float((merged['sd'] - merged[f'{prefix}{estimand}_paired_sd']).abs().max()),
                        'max_miss_difference': miss})
    result = pd.DataFrame(out)
    if result.empty or (result[['max_mean_difference', 'max_sd_difference']] > 1e-9).any().any() \
            or (result.max_miss_difference.dropna() > 1e-12).any():
        raise ValueError('Planning table disagrees with committed paired-contrast exports')
    return result


def candidate_precision(table_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in CANDIDATES:
        g = table_rows[(table_rows.arm == c['arm']) & (table_rows.comparator == c['comparator']) & (table_rows.condition == c['condition'])
                       & (table_rows.bank == c['bank']) & (table_rows.estimand == c['estimand'])]
        if len(g) != 4:
            raise ValueError(f"Expected four training trials for {c['id']}")
        ref = g[g.seed == REFERENCE_SEED].iloc[0]
        sd = float(g.sd.max())
        row = {**c, 'reference_mean': float(ref['mean']), 'trial_mean_min': float(g['mean'].min()), 'trial_mean_max': float(g['mean'].max()),
               'reference_sd': float(ref.sd), 'planning_sd': sd, 'reference_se_n1000': float(ref.se),
               'positives_reference': int(ref.positives), 'skewness_reference': float(ref.skewness),
               'exact_zero_fraction_reference': float(ref.exact_zero_fraction)}
        for h in HALF_WIDTHS:
            row[f'n_half_width_{h:g}'] = n_for_half_width(sd, h)
        effect = abs(float(ref['mean']))
        for share in (1.0, 0.5):
            for margin in MARGINS:
                row[f'n_power90_effect{share:g}_margin{margin:g}'] = n_for_margin(sd, share * effect, margin)
        rows.append(row)
    return pd.DataFrame(rows)


def simulation_checks(cache: dict, rng: np.random.Generator) -> pd.DataFrame:
    """Resample the reference trial's per-scenario contrasts for primary/secondary candidates."""
    rows = []
    for c in CANDIDATES:
        values = contrast(cache[(REFERENCE_SEED, c['bank'])], c['arm'], c['comparator'], c['condition'], c['estimand']).to_numpy()
        effect = float(values.mean())
        sign = 1.0 if effect >= 0 else -1.0
        oriented = sign * values  # margins are stated in the direction of the development effect
        size = abs(effect)
        for n in N_GRID:
            means, ses = resample_moments(oriented, n, rng)
            for margin in MARGINS:
                for name, shift in (('development_effect', 0.0), ('half_effect', -size / 2), ('boundary_null', margin - size)):
                    rows.append({'id': c['id'], 'scenario': name,
                                 'orientation': 'development effect sign' if sign > 0 else 'reversed sign',
                                 **interval_properties(means + shift, ses, n, size + shift, margin)})
    return pd.DataFrame(rows)


def miss_precision(table_rows: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    for c in CANDIDATES:
        ref = table_rows[(table_rows.seed == REFERENCE_SEED) & (table_rows.arm == c['arm']) & (table_rows.comparator == c['comparator'])
                         & (table_rows.condition == c['condition']) & (table_rows.bank == c['bank']) & (table_rows.estimand == c['estimand'])].iloc[0]
        prevalence = ref.positives / ref.scenarios
        endpoints = ({'endpoint': 'new misses versus comparator at condition', 'count': ref.new_misses, 'reverse': ref.recovered_misses}
                     if c['estimand'] == 'absolute' else
                     {'endpoint': 'reuse-induced new misses of arm (condition versus no reuse)', 'count': ref.reuse_new_misses_arm,
                      'reverse': ref.reuse_recovered_misses_arm})
        rate = endpoints['count'] / ref.positives
        for n in N_GRID:
            positives = int(round(n * prevalence))
            row = {'id': c['id'], 'endpoint': endpoints['endpoint'], 'development_positives': int(ref.positives),
                   'development_new_misses': int(endpoints['count']), 'development_recovered_misses': int(endpoints['reverse']),
                   'development_new_miss_rate': rate, 'planned_scenarios': n, 'expected_positives': positives,
                   'expected_upper_bound_at_development_rate': clopper_pearson_upper(int(round(rate * positives)), positives),
                   'upper_bound_zero_new_misses': clopper_pearson_upper(0, positives)}
            for margin in MISS_MARGINS:
                row[f'p_upper_bound_below_{margin:g}'] = miss_bound_power(rate, positives, margin, rng)
            rows.append(row)
    return pd.DataFrame(rows)


def trial_spread(table_rows: pd.DataFrame) -> pd.DataFrame:
    """Between-trial spread (training sensitivity) next to within-trial evaluation SE."""
    keys = ['bank', 'arm', 'comparator', 'condition', 'estimand']
    g = table_rows.groupby(keys)
    return (g.agg(trials=('seed', 'size'), mean_of_trials=('mean', 'mean'), between_trial_sd=('mean', 'std'),
                  within_trial_se_median=('se', 'median')).reset_index())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--bundles', type=Path, default=Path('docs/research/results'))
    parser.add_argument('--seed', type=int, default=20261040)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    runs = {run_id: (RUN_ROOT / run_id).resolve() for run_id in SOURCES}
    audits = [audit_run(path) for path in runs.values()]
    config = {'sources': list(SOURCES), 'regime': REGIME, 'reference_seed': REFERENCE_SEED, 'candidates': list(CANDIDATES),
              'half_widths': list(HALF_WIDTHS), 'margins': list(MARGINS), 'n_grid': list(N_GRID), 'resamples': RESAMPLES,
              'miss_margins': list(MISS_MARGINS), 'alpha': ALPHA, 'power': POWER, 'resampling_seed': args.seed,
              'clipping': 1e-6, 'fitting': 'none', 'scientific_bank': 'not generated'}
    with Run(args.run_id, 'precision_planning', config, [p / 'manifest.json' for p in runs.values()]) as run:
        rng = np.random.default_rng(args.seed)
        predictions = load_predictions(runs)
        rows, cache = planning_table(predictions)
        checks = reconcile(rows, args.bundles)
        candidates = candidate_precision(rows)
        simulated = simulation_checks(cache, rng)
        misses = miss_precision(rows, rng)
        spread = trial_spread(rows)
        out = run.path
        rows.to_csv(out / 'planning_table.csv', index=False)
        checks.to_csv(out / 'reconciliation.csv', index=False)
        candidates.to_csv(out / 'candidate_precision.csv', index=False)
        simulated.to_csv(out / 'resampling_checks.csv', index=False)
        misses.to_csv(out / 'miss_precision.csv', index=False)
        spread.to_csv(out / 'trial_spread.csv', index=False)
        write_json(out / 'audit.json', {'source_runs': audits, 'matched_prediction_rows': len(predictions),
                   'planning_rows': len(rows), 'reconciled_export_rows': int(checks.rows.sum()),
                   'max_reconciliation_difference': float(checks[['max_mean_difference', 'max_sd_difference']].max().max()),
                   'fitting_performed': False, 'scientific_bank_opened': False,
                   'scope': 'Development planning on exposed banks; not V03 freeze or scientific inference.'})
        (out / 'report.md').write_text(report(rows, checks, candidates, simulated, misses, spread, args.run_id), encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('audit.json', 'candidate_precision.csv', 'miss_precision.csv', 'planning_table.csv', 'reconciliation.csv',
             'report.md', 'resampling_checks.csv', 'trial_spread.csv')
    provenance = {'run_id': args.run_id, 'source_runs': list(SOURCES), 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


def candidate_label(c) -> str:
    return f"{c['arm']} vs {c['comparator']}, {c['estimand']}, {c['condition']}, {c['bank']}"


def report(rows, checks, candidates, simulated, misses, spread, run_id) -> str:
    software = rows[(rows.arm == 'singleton') & (rows.comparator == 'latest_metadata') & (rows.bank == 'software')]
    by_condition = (software.groupby(['estimand', 'condition'])['mean'].agg(['min', 'max']).reset_index()
                    .rename(columns={'min': 'trial_min', 'max': 'trial_max'}))
    cand = candidates.assign(contrast=candidates.apply(candidate_label, axis=1))
    sim = simulated[simulated.margin.isin([0.0, 0.02])]
    p1 = sim[(sim.id == 'P1')].pivot_table(index=['n'], columns=['scenario', 'margin'], values='lower_above_margin')
    p1.columns = [f'{s}_m{m:g}' for s, m in p1.columns]
    # A location shift makes the boundary-null rate identical for every margin.
    p1 = p1.drop(columns=['boundary_null_m0']).reset_index()
    widths = simulated[(simulated.id == 'P1') & (simulated.scenario == 'development_effect') & (simulated.margin == 0)][['n', 'coverage', 'half_width_median', 'half_width_p95']]
    p1 = p1.merge(widths, on='n')
    nulls = (simulated[simulated.scenario == 'boundary_null'].groupby('id')
             .agg(coverage_min=('coverage', 'min'), coverage_max=('coverage', 'max'),
                  false_confirm_max=('lower_above_margin', 'max'), false_dismiss_max=('upper_below_margin', 'max')).reset_index())
    miss = misses[misses.id.isin(['P1', 'S1', 'S6']) & misses.planned_scenarios.isin([1000, 5000])]
    keys = pd.DataFrame(list(CANDIDATES))[['id', 'bank', 'arm', 'comparator', 'condition', 'estimand']]
    spread_c = spread.merge(keys, on=['bank', 'arm', 'comparator', 'condition', 'estimand'])
    spread_c = spread_c.assign(evaluation_se_n5000=spread_c.within_trial_se_median * math.sqrt(1000 / 5000)).sort_values('id')
    return f'''# V02 precision planning: candidate scientific contrasts

Date: 10 October 2026. Run `{run_id}`. **Development planning on exposed banks.
No model was fitted, no scenario was generated and the scientific reservation
(seed 20261012, IDs scientific:00000..04999) was not opened.** The chosen primary
contrast and its rationale are recorded separately in
`docs/research/execution/primary_contrast.md`.

## Inputs and reconciliation

All four class-forecast source runs pass manifest, input and archived-source
checks. The planning table recomputes {len(rows):,} matched-training paired contrasts
(training trial x bank x condition x arm pair x estimand) from audited per-scenario
predictions (clipped log loss at 1e-6; review at the nominal 95% training-recall
threshold). Every overlapping row of the committed paired-contrast exports
reconciles:

{table(checks, ['bundle', 'estimand', 'rows', 'max_mean_difference', 'max_sd_difference', 'max_miss_difference'])}

Each row records its exact scenario set by first/last ID and a SHA-256 of the
sorted IDs ({rows.case_ids_sha256.nunique()} distinct scenario sets for {rows.bank.nunique()} banks).
Each bank has 1,000 evaluation scenarios, the independent unit. The three
800-scenario training subsets overlap the full-reference cohort; the four trials
describe training sensitivity, not independent replication.

## What the development banks show

Singleton history summary minus latest-message metadata, software bank, matched
training (range over the four training trials). Negative absolute values favor the
history model. Degradation is the change relative to no reuse.

{table(by_condition, ['estimand', 'condition', 'trial_min', 'trial_max'])}

Latest-message arms are exactly invariant to every reuse condition because the
latest window is matched by construction, so a degradation contrast against
them equals the history model's own reuse-induced loss change.

## Candidate contrasts and normal-approximation sample sizes

`planning_sd` is the largest paired SD over the four trials. `n_half_width_h`
gives scenarios for a two-sided 95% interval of half-width h. `n_power90_effectS_marginM`
gives scenarios for 90% probability that the lower bound exceeds margin M when
the true contrast is S times the development reference effect (in its observed
direction); `inf` means that effect does not exceed the margin.

{table(cand, ['id', 'contrast', 'reference_mean', 'trial_mean_min', 'trial_mean_max', 'planning_sd', 'skewness_reference', 'positives_reference'])}

{table(cand, ['id', 'n_half_width_0.01', 'n_half_width_0.02', 'n_power90_effect1_margin0', 'n_power90_effect1_margin0.02', 'n_power90_effect0.5_margin0', 'n_power90_effect0.5_margin0.01', 'n_power90_effect0.5_margin0.02'])}

## Resampling check of the t-interval for P1

{RESAMPLES} resamples of n scenarios from the reference trial's per-scenario P1
differences, oriented in the development effect direction. Columns give the
probability that the lower 95% bound exceeds the margin (0 or 0.02) when the true
contrast is the development effect, half of it, or exactly the margin
(`boundary_null`, a false confirmation rate with nominal value 0.025).

{table(p1, list(p1.columns))}

Across all candidates and sample sizes at their boundary nulls:

{table(nulls, ['id', 'coverage_min', 'coverage_max', 'false_confirm_max', 'false_dismiss_max'])}

`false_dismiss` is the probability that the upper bound falls below a margin equal
to the truth (nominal 0.025). Right-skewed differences make the upper bound
anti-conservative at small n and the lower bound conservative. The final interval
method belongs to the §3 analysis specification.

## Miss endpoints

Miss contrasts use positive scenarios only. For degradation candidates, the
endpoint is reuse-induced new misses of the history arm (missed under the
condition but reviewed without reuse); the latest-message comparator cannot change.
The Clopper-Pearson column is the one-sided 95% upper bound at the development
rate; the last columns give the probability that it falls below each margin.

{table(miss, ['id', 'endpoint', 'development_new_misses', 'development_recovered_misses', 'planned_scenarios', 'expected_positives', 'expected_upper_bound_at_development_rate', 'p_upper_bound_below_0.01', 'p_upper_bound_below_0.05'])}

The bound is the exact one-sided Clopper-Pearson limit, `Beta^-1(0.95; k+1, n-k)`
(Clopper and Pearson, Biometrika 26:404-413, 1934), as specified in Report 2
§7.2. The tests check its zero-failure identity, `1 - 0.05^(1/n)`.

These are not noninferiority endpoints. Reuse produces new misses in development,
so the informative quantity is the estimated reuse-induced miss rate and its
interval, reported secondarily. The nominal training-recall threshold is not a
miss guarantee.

## Training sensitivity versus evaluation precision

{table(spread_c, ['id', 'trials', 'mean_of_trials', 'between_trial_sd', 'within_trial_se_median', 'evaluation_se_n5000'])}

The between-trial SD comes from overlapping subsets of one development bank, so it
understates variation across independent training banks. It is nevertheless
comparable to the evaluation SE expected at 5,000 scenarios. §3 must decide
whether inference is conditional on one fitted model or averages over independent
training banks.

## Limits

- Development banks are exposed and isotropic; the candidate scientific
  configuration is anisotropic. Effects and SDs may change (§4).
- Resampling treats the 1,000 development scenarios as the population; it checks
  approximation quality, not scientific coverage.
- Enriched synthetic prevalence (software 19.4%, bias 32.6%) is not operational
  workload; review and miss rates are stress-population quantities.
- Same-workflow analysis, not independent A03 review.
'''


if __name__ == '__main__':
    main()
