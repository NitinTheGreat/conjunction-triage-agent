"""Development validation of interval methods for skewed scenario-paired contrasts.

Draws evaluation samples from the exposed development distribution of each
candidate contrast (reference training trial) and records one-sided error rates
of the Student t interval and the studentized (bootstrap-t) interval. Both
intervals are location-equivariant, so error rates relative to the sampling
distribution's own mean equal those at any decision boundary reached by a
location shift. Fits nothing and opens no scientific scenario.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from scipy import stats

from research.artifacts import RUN_ROOT, Run, sha256, write_json
from research.precision_planning import REFERENCE_SEED, SOURCES, contrast, load_predictions, paired_frames
from research.summarize_pilot import audit_run, table

CANDIDATES = (
    ('P1', 'singleton', 'latest_metadata', 'overlap_90', 'degradation', 'software'),
    ('S1', 'singleton', 'latest_metadata', 'overlap_90', 'absolute', 'software'),
    ('S6', 'singleton', 'latest_metadata', 'solution_reissue', 'absolute', 'software'),
)
DESIGN = ((1000, 4000), (5000, 1500))  # (evaluation scenarios, outer replicates)
INNER = 999
ALPHA = 0.05


def t_interval(x: np.ndarray, alpha: float = ALPHA) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    se = x.std(ddof=1) / math.sqrt(len(x))
    half = stats.t.ppf(1 - alpha / 2, len(x) - 1) * se
    return float(x.mean() - half), float(x.mean() + half)


def bootstrap_t_interval(x: np.ndarray, resamples: int, rng: np.random.Generator, alpha: float = ALPHA) -> dict:
    """Studentized bootstrap: invert quantiles of (mean* - mean) / se*.

    Lower = mean - q(1 - alpha/2) se and upper = mean - q(alpha/2) se, so right
    skew moves both endpoints upward relative to the symmetric t interval.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    mean, se = x.mean(), x.std(ddof=1) / math.sqrt(n)
    if not se > 0:
        raise ValueError('A studentized interval needs nonconstant data')
    draw = x[rng.integers(0, n, size=(resamples, n), dtype=np.int32)]
    se_star = draw.std(axis=1, ddof=1) / math.sqrt(n)
    if np.any(se_star <= 0):
        raise ValueError('Degenerate bootstrap resample')
    t_star = (draw.mean(axis=1) - mean) / se_star
    upper_q, lower_q = np.quantile(t_star, [1 - alpha / 2, alpha / 2])
    percentile = np.quantile(draw.mean(axis=1), [alpha / 2, 1 - alpha / 2])
    return {'lower': float(mean - upper_q * se), 'upper': float(mean - lower_q * se),
            'percentile_lower': float(percentile[0]), 'percentile_upper': float(percentile[1])}


def validate(values: np.ndarray, n: int, outer: int, rng: np.random.Generator, inner: int = INNER) -> dict:
    truth = float(np.mean(values))
    rows = {'t': [], 'bootstrap_t': [], 'percentile': []}
    for _ in range(outer):
        sample = values[rng.integers(0, len(values), size=n, dtype=np.int32)]
        rows['t'].append(t_interval(sample))
        b = bootstrap_t_interval(sample, inner, rng)
        rows['bootstrap_t'].append((b['lower'], b['upper']))
        rows['percentile'].append((b['percentile_lower'], b['percentile_upper']))
    out = []
    for method, bounds in rows.items():
        a = np.asarray(bounds)
        out.append({'method': method, 'n': n, 'outer_replicates': outer, 'inner_resamples': inner,
                    'false_low_side': float(np.mean(a[:, 0] > truth)), 'false_high_side': float(np.mean(a[:, 1] < truth)),
                    'coverage': float(np.mean((a[:, 0] <= truth) & (truth <= a[:, 1]))),
                    'median_half_width': float(np.median((a[:, 1] - a[:, 0]) / 2)),
                    'mc_se_one_side_at_nominal': math.sqrt(ALPHA / 2 * (1 - ALPHA / 2) / outer)})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261041)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    runs = {r: (RUN_ROOT / r).resolve() for r in SOURCES}
    audits = [audit_run(p) for p in runs.values()]
    config = {'sources': list(SOURCES), 'reference_seed': REFERENCE_SEED, 'candidates': [list(c) for c in CANDIDATES],
              'design': [list(d) for d in DESIGN], 'inner_resamples': INNER, 'alpha': ALPHA, 'seed': args.seed,
              'fitting': 'none', 'scientific_bank': 'not generated'}
    with Run(args.run_id, 'interval_validation', config, [p / 'manifest.json' for p in runs.values()]) as run:
        rng = np.random.default_rng(args.seed)
        predictions = load_predictions(runs)
        rows = []
        for cid, arm, comparator, condition, estimand, bank in CANDIDATES:
            group = predictions[(predictions.seed == REFERENCE_SEED) & (predictions.bank == bank)]
            values = contrast(paired_frames(group), arm, comparator, condition, estimand).to_numpy()
            for n, outer in DESIGN:
                for r in validate(values, n, outer, rng):
                    rows.append({'id': cid, 'skewness': float(stats.skew(values)), **r})
                print('DONE', cid, n, flush=True)
        result = pd.DataFrame(rows)
        result.to_csv(run.path / 'interval_validation.csv', index=False)
        write_json(run.path / 'audit.json', {'source_runs': audits, 'rows': len(result), 'fitting_performed': False,
                                             'scientific_bank_opened': False})
        (run.path / 'report.md').write_text(f'''# Interval-method validation under right skew

Run `{args.run_id}`. Development per-scenario contrasts from the reference training
trial (exposed banks). Each outer replicate draws n scenarios with replacement
from the 1,000 development values; the truth is their mean. `false_low_side` is
P(lower bound > truth) and `false_high_side` is P(upper bound < truth); each is
nominally {ALPHA / 2}. A confirmation decision uses the lower bound and a
"not material" decision the upper bound. The bootstrap-t uses {INNER} inner
resamples here; the scientific analysis would use more.

{table(result, ['id', 'skewness', 'method', 'n', 'outer_replicates', 'false_low_side', 'false_high_side', 'coverage', 'median_half_width', 'mc_se_one_side_at_nominal'])}

Location equivariance makes these rates apply at any decision boundary reached by
shifting the distribution. They do not cover shape changes in an unseen
configuration.
''', encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    provenance = {'run_id': args.run_id, 'source_runs': list(SOURCES), 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in ('audit.json', 'interval_validation.csv', 'report.md'):
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


if __name__ == '__main__':
    main()
