"""Frozen-analysis building blocks for the Track R contrasts (V03 candidate).

Studentized-bootstrap intervals and one-sided p-values over whole scenarios,
the primary three-way margin decision, Holm's step-down procedure for the
confirmatory secondary family, and exact summaries for reuse-induced misses.
Pure functions: no file access and no knowledge of how scenarios were generated.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

ALPHA = 0.05


def studentized_bootstrap(values, resamples: int, seed: int, alpha: float = ALPHA) -> dict:
    """Bootstrap-t over scenarios: interval plus the resampled t* distribution."""
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or len(x) < 3 or not np.isfinite(x).all():
        raise ValueError('Expected at least three finite per-scenario values')
    n = len(x)
    mean, se = float(x.mean()), float(x.std(ddof=1) / math.sqrt(n))
    if not se > 0:
        raise ValueError('A studentized interval needs nonconstant values')
    rng = np.random.default_rng(seed)
    t_star = np.empty(resamples)
    chunk = max(1, min(resamples, 2_000_000 // n))
    for start in range(0, resamples, chunk):
        size = min(chunk, resamples - start)
        draw = x[rng.integers(0, n, size=(size, n))]
        se_star = draw.std(axis=1, ddof=1) / math.sqrt(n)
        if np.any(se_star <= 0):
            raise ValueError('Degenerate bootstrap resample')
        t_star[start:start + size] = (draw.mean(axis=1) - mean) / se_star
    upper_q, lower_q = np.quantile(t_star, [1 - alpha / 2, alpha / 2])
    t_crit = stats.t.ppf(1 - alpha / 2, n - 1)
    return {'n': n, 'mean': mean, 'se': se, 'lower': mean - float(upper_q) * se, 'upper': mean - float(lower_q) * se,
            't_lower': mean - t_crit * se, 't_upper': mean + t_crit * se, 'resamples': resamples, 'seed': seed,
            't_star': t_star}


def one_sided_p(result: dict, null_value: float, alternative: str) -> float:
    """Bootstrap-t p-value; alternative 'greater' tests H0: theta <= null_value."""
    observed = (result['mean'] - null_value) / result['se']
    t_star = result['t_star']
    if alternative == 'greater':
        extreme = np.count_nonzero(t_star >= observed)
    elif alternative == 'less':
        extreme = np.count_nonzero(t_star <= observed)
    else:
        raise ValueError(alternative)
    return (1 + extreme) / (1 + len(t_star))


def primary_decision(result: dict, margin: float) -> str:
    """Report 2 / primary-contrast rule on the two-sided 95% interval."""
    if result['lower'] > margin:
        return 'material_degradation_confirmed'
    if result['upper'] < margin:
        return 'not_material'
    return 'inconclusive'


def holm(p_values: dict[str, float], alpha: float = ALPHA) -> dict[str, bool]:
    """Holm step-down: reject in increasing p order until the first failure."""
    if any(not 0 <= p <= 1 for p in p_values.values()):
        raise ValueError('p-values must lie in [0, 1]')
    order = sorted(p_values, key=lambda k: (p_values[k], k))
    m, rejected, stop = len(order), {}, False
    for j, key in enumerate(order):
        stop = stop or p_values[key] > alpha / (m - j)
        rejected[key] = not stop
    return rejected


def clopper_pearson(successes: int, trials: int, alpha: float = ALPHA) -> tuple[float, float]:
    """Two-sided exact interval for a binomial proportion."""
    if trials <= 0 or not 0 <= successes <= trials:
        raise ValueError('Need 0 <= successes <= trials and trials > 0')
    lower = 0.0 if successes == 0 else float(stats.beta.ppf(alpha / 2, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(stats.beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    return lower, upper


def reuse_miss_summary(new_misses: int, recovered_misses: int, positives: int) -> dict:
    """Reuse-induced miss rate with an exact interval and an exact McNemar p-value."""
    if positives <= 0:
        return {'status': 'undefined_no_positives'}
    lower, upper = clopper_pearson(new_misses, positives)
    discordant = new_misses + recovered_misses
    mcnemar = float(stats.binomtest(new_misses, discordant, .5).pvalue) if discordant else 1.0
    return {'status': 'finite', 'positives': positives, 'new_misses': new_misses, 'recovered_misses': recovered_misses,
            'new_miss_rate': new_misses / positives, 'new_miss_rate_lower95': lower, 'new_miss_rate_upper95': upper,
            'net_miss_difference': (new_misses - recovered_misses) / positives, 'exact_mcnemar_p': mcnemar}
