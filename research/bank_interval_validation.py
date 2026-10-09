"""Validate the bank-combined interval on designs simulated from development components.

Uses the completed sensitivity campaign's isotropic own-configuration predictions
(six independent training banks, 2,000 evaluation scenarios). For each contrast it
estimates scenario effects (empirical, skewed), the bank SD (two-way moments) and
interaction residuals (empirical). It then simulates K-bank x n-scenario designs
with a known mean and records one-sided error rates of (a) the bank-combined
interval and (b) a scenario-only bootstrap-t that ignores training-bank variance.
Bank effects are drawn as normal: six banks cannot validate their shape.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json
from research.summarize_pilot import audit_run, table
from research.summarize_sensitivity import CANDIDATES, bank_contrasts, two_way_components
from research.track_r_analysis import bank_combined_interval, studentized_bootstrap

CONTRASTS = ('P1', 'S2', 'S6')
DESIGNS = ((10, 5000, 1000), (5, 5000, 1000), (10, 2000, 1000))  # banks, scenarios, replicates
INNER = 999


def components_from(matrix: np.ndarray) -> dict:
    d = np.asarray(matrix, dtype=float)
    grand = d.mean()
    rows, cols = d.mean(axis=1), d.mean(axis=0)
    parts = two_way_components(d)
    return {'scenario_effects': rows - grand, 'residuals': (d - rows[:, None] - cols[None, :] + grand).ravel(),
            'bank_sd': float(np.sqrt(parts['var_bank'])), 'grand_mean': float(grand), **parts}


def simulate(parts: dict, banks: int, scenarios: int, truth: float, rng: np.random.Generator) -> np.ndarray:
    a = rng.choice(parts['scenario_effects'], size=scenarios, replace=True)
    b = rng.normal(0, parts['bank_sd'], size=banks)
    e = rng.choice(parts['residuals'], size=(scenarios, banks), replace=True)
    return truth + a[:, None] + b[None, :] + e


def validate(parts: dict, banks: int, scenarios: int, replicates: int, rng: np.random.Generator) -> list[dict]:
    truth = parts['grand_mean']
    out = {'bank_combined': [], 'scenario_only': []}
    for _ in range(replicates):
        d = simulate(parts, banks, scenarios, truth, rng)
        seed = int(rng.integers(0, 2 ** 31 - 1))
        combined = bank_combined_interval(d, INNER, seed)
        out['bank_combined'].append((combined['lower'], combined['upper']))
        out['scenario_only'].append((combined['scenario_lower'], combined['scenario_upper']))
    rows = []
    for method, bounds in out.items():
        a = np.asarray(bounds)
        rows.append({'method': method, 'banks': banks, 'scenarios': scenarios, 'replicates': replicates,
                     'false_low_side': float(np.mean(a[:, 0] > truth)), 'false_high_side': float(np.mean(a[:, 1] < truth)),
                     'coverage': float(np.mean((a[:, 0] <= truth) & (truth <= a[:, 1]))),
                     'median_half_width': float(np.median((a[:, 1] - a[:, 0]) / 2))})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20261043)
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    source = args.source.resolve()
    source_audit = audit_run(source)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['kind'] != 'sensitivity_development':
        raise ValueError('Expected the completed sensitivity campaign')
    base = manifest['config']['transfer_source']
    config = {'source': str(source), 'configuration': base, 'contrasts': list(CONTRASTS), 'designs': [list(d) for d in DESIGNS],
              'inner_resamples': INNER, 'seed': args.seed, 'bank_effects': 'normal with the two-way moment SD'}
    with Run(args.run_id, 'bank_interval_validation', config, [source / 'manifest.json']) as run:
        rng = np.random.default_rng(args.seed)
        predictions = read_table(source / 'predictions.parquet')
        own = predictions[(predictions.training_configuration == base) & (predictions.evaluation_configuration == base)]
        _, matrices = bank_contrasts(own)
        rows, inputs = [], []
        for cid in CONTRASTS:
            banks = sorted(b for (t, e, c, b) in matrices if c == cid)
            matrix = np.column_stack([matrices[(base, base, cid, b)].to_numpy() for b in banks])
            parts = components_from(matrix)
            inputs.append({'id': cid, 'banks': len(banks), 'scenarios': matrix.shape[0], 'grand_mean': parts['grand_mean'],
                           'bank_sd': parts['bank_sd'], 'var_scenario': parts['var_scenario'], 'var_interaction': parts['var_interaction']})
            for k, n, r in DESIGNS:
                rows.extend({'id': cid, **row} for row in validate(parts, k, n, r, rng))
                print('DONE', cid, k, n, flush=True)
        result, inputs = pd.DataFrame(rows), pd.DataFrame(inputs)
        result.to_csv(run.path / 'bank_interval_validation.csv', index=False)
        inputs.to_csv(run.path / 'simulation_inputs.csv', index=False)
        write_json(run.path / 'audit.json', {'source_run': source_audit, 'rows': len(result), 'fitting_performed': False,
                                             'scientific_bank_opened': False})
        (run.path / 'report.md').write_text(f'''# Bank-combined interval validation

Run `{args.run_id}` from `{source.name}` (`{base}` own-configuration predictions,
six independent training banks). Designs are simulated from the measured
components: empirical scenario effects, normal bank effects with the moment SD,
and empirical interaction residuals. The truth is the development grand mean.
Nominal error is 0.025 per side; Monte Carlo SE about 0.005 at 1,000 replicates.

{table(inputs, ['id', 'banks', 'scenarios', 'grand_mean', 'bank_sd', 'var_scenario', 'var_interaction'])}

{table(result, ['id', 'method', 'banks', 'scenarios', 'replicates', 'false_low_side', 'false_high_side', 'coverage', 'median_half_width'])}

`scenario_only` is the bootstrap-t on bank-averaged contrasts without the bank
term, that is, inference conditional on the fitted banks. Normal bank effects
are an assumption; six development banks cannot check their shape.
''', encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    provenance = {'run_id': args.run_id, 'source_runs': [source.name], 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in ('audit.json', 'bank_interval_validation.csv', 'report.md', 'simulation_inputs.csv'):
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


if __name__ == '__main__':
    main()
