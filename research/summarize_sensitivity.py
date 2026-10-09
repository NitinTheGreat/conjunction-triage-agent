"""Summarize the development sensitivity campaign for the V03 design.

Computes the prespecified contrasts per configuration and independent training
bank, a two-way random-effects variance decomposition across isotropic banks,
persistence relative to the proposed margin, and transfer of isotropic-trained
models. Everything is exposed development evidence; nothing here is confirmation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd
from scipy import stats

from research.artifacts import Run, read_table, sha256, write_json
from research.metrics import class_metrics
from research.precision_planning import contrast, describe, discordance, paired_frames
from research.summarize_pilot import audit_run, table

CANDIDATES = (
    ('P1', 'singleton', 'latest_metadata', 'overlap_90', 'degradation'),
    ('S1', 'singleton', 'latest_metadata', 'overlap_90', 'absolute'),
    ('S2', 'grouped', 'singleton', 'overlap_90', 'degradation'),
    ('S3', 'oracle_lineage_weight', 'singleton', 'overlap_90', 'degradation'),
    ('S5', 'singleton', 'latest_metadata', 'solution_reissue', 'degradation'),
    ('S6', 'singleton', 'latest_metadata', 'solution_reissue', 'absolute'),
)
MARGIN = 0.02
DESIGNS = tuple((k, n) for k in (1, 3, 5, 10) for n in (2000, 5000))


def two_way_components(matrix: np.ndarray) -> dict:
    """Random-effects variance components for scenarios x banks, one value per cell.

    d[i, k] = mu + a_i + b_k + e_ik. Negative moment estimates are truncated at zero
    and flagged; the truncation is reported, not hidden.
    """
    d = np.asarray(matrix, dtype=float)
    n, k = d.shape
    if n < 2 or k < 2 or not np.isfinite(d).all():
        raise ValueError('Need at least two scenarios, two banks and finite values')
    grand = d.mean()
    rows, cols = d.mean(axis=1), d.mean(axis=0)
    ms_scenario = k * np.sum((rows - grand) ** 2) / (n - 1)
    ms_bank = n * np.sum((cols - grand) ** 2) / (k - 1)
    residual = d - rows[:, None] - cols[None, :] + grand
    ms_residual = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    raw_scenario, raw_bank = (ms_scenario - ms_residual) / k, (ms_bank - ms_residual) / n
    return {'scenarios': n, 'banks': k, 'grand_mean': float(grand), 'bank_means_sd': float(cols.std(ddof=1)),
            'var_scenario': float(max(raw_scenario, 0.)), 'var_bank': float(max(raw_bank, 0.)),
            'var_interaction': float(ms_residual),
            'scenario_truncated': bool(raw_scenario < 0), 'bank_truncated': bool(raw_bank < 0)}


def projected_se(components: dict, banks: int, scenarios: int) -> float:
    """SE of the bank-averaged contrast for independent banks sharing evaluation scenarios."""
    return math.sqrt(components['var_scenario'] / scenarios + components['var_bank'] / banks
                     + components['var_interaction'] / (scenarios * banks))


def bank_contrasts(predictions: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows, matrices = [], {}
    for (train_config, bank, eval_config), group in predictions.groupby(['training_configuration', 'training_bank', 'evaluation_configuration']):
        pivots = paired_frames(group)
        for cid, arm, comparator, condition, estimand in CANDIDATES:
            values = contrast(pivots, arm, comparator, condition, estimand)
            matrices[(train_config, eval_config, cid, bank)] = values
            stats_ = describe(values)
            t = stats.t.ppf(.975, stats_['scenarios'] - 1)
            rows.append({'training_configuration': train_config, 'training_bank': bank, 'evaluation_configuration': eval_config,
                         'id': cid, 'arm': arm, 'comparator': comparator, 'condition': condition, 'estimand': estimand,
                         'positives': int(pivots['y'].sum()), **stats_,
                         'lower95': stats_['mean'] - t * stats_['se'], 'upper95': stats_['mean'] + t * stats_['se'],
                         **discordance(pivots, arm, comparator, condition)})
    return pd.DataFrame(rows), matrices


def variance_study(matrices: dict, configuration: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    components, projections = [], []
    for cid, *_ in CANDIDATES:
        banks = sorted(b for (t, e, c, b) in matrices if t == configuration and e == configuration and c == cid)
        series = [matrices[(configuration, configuration, cid, b)] for b in banks]
        index = series[0].index
        if any(not s.index.equals(index) for s in series):
            raise ValueError('Banks must share evaluation scenarios')
        result = two_way_components(np.column_stack([s.to_numpy() for s in series]))
        components.append({'id': cid, 'configuration': configuration, **result,
                           'evaluation_se_one_bank_n2000': projected_se(result, 1, 2000)})
        for k, n in DESIGNS:
            projections.append({'id': cid, 'configuration': configuration, 'independent_training_banks': k,
                                'evaluation_scenarios': n, 'projected_se': projected_se(result, k, n),
                                'projected_half_width': 1.96 * projected_se(result, k, n),
                                'conditional_on_fit_se': math.sqrt((result['var_scenario'] + result['var_interaction'] / k) / n)})
    return pd.DataFrame(components), pd.DataFrame(projections)


def persistence(contrasts: pd.DataFrame) -> pd.DataFrame:
    own = contrasts[contrasts.training_configuration == contrasts.evaluation_configuration]
    return (own.groupby(['training_configuration', 'id', 'estimand']).agg(
        banks=('training_bank', 'size'), mean_min=('mean', 'min'), mean_max=('mean', 'max'),
        lower_above_margin=('lower95', lambda v: int((v > MARGIN).sum())), lower_above_zero=('lower95', lambda v: int((v > 0).sum())),
        upper_below_zero=('upper95', lambda v: int((v < 0).sum())), positives=('positives', 'first')).reset_index())


def transfer(contrasts: pd.DataFrame, source: str) -> pd.DataFrame:
    trained = contrasts[contrasts.training_configuration == source]
    native = contrasts[contrasts.training_configuration == contrasts.evaluation_configuration]
    a = trained.groupby(['evaluation_configuration', 'id']).agg(transfer_mean=('mean', 'mean'), transfer_min=('mean', 'min'),
                                                                 transfer_max=('mean', 'max')).reset_index()
    b = native.groupby(['evaluation_configuration', 'id']).agg(native_mean=('mean', 'mean')).reset_index()
    return a.merge(b, on=['evaluation_configuration', 'id'], how='left')


def check_metrics(predictions: pd.DataFrame, saved: pd.DataFrame) -> int:
    """Regenerate every saved class-metric row from predictions."""
    keys = ['training_configuration', 'training_bank', 'evaluation_configuration', 'arm', 'condition']
    checked = 0
    for key, group in predictions.groupby(keys):
        row = saved.loc[(saved[keys] == pd.Series(dict(zip(keys, key)))).all(axis=1)]
        if len(row) != 1:
            raise ValueError(f'Missing or duplicate metric row: {key}')
        expected = class_metrics(group.y.to_numpy(), group.q.to_numpy(), group.review95.to_numpy())
        for name in ('n', 'positives', 'reviewed', 'fn', 'log_loss', 'brier'):
            if not np.isclose(row.iloc[0][name], expected[name], rtol=0, atol=1e-12):
                raise ValueError(f'Metric mismatch for {key}: {name}')
        checked += 1
    return checked


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
    if manifest['kind'] != 'sensitivity_development':
        raise ValueError('Expected a completed sensitivity campaign')
    contract = manifest['config']
    with Run(args.run_id, 'sensitivity_summary', {'source': str(source)}, [source / 'manifest.json']) as run:
        predictions = read_table(source / 'predictions.parquet')
        if len(predictions) != contract['planned_prediction_rows']:
            raise ValueError('Prediction count disagrees with the contract')
        checked = check_metrics(predictions, pd.read_csv(source / 'metrics.csv'))
        selections = json.loads((source / 'selections.json').read_text(encoding='utf-8'))
        generation = pd.DataFrame(json.loads((source / 'generation.json').read_text(encoding='utf-8')))
        contrasts, matrices = bank_contrasts(predictions)
        components, projections = variance_study(matrices, contract['transfer_source'])
        persist = persistence(contrasts)
        moved = transfer(contrasts, contract['transfer_source'])
        selected = pd.DataFrame([{k: s[k] for k in ('configuration', 'training_bank', 'arm', 'C', 'seconds')} for s in selections])
        out = run.path
        contrasts.drop(columns=[]).to_csv(out / 'bank_contrasts.csv', index=False)
        components.to_csv(out / 'variance_components.csv', index=False)
        projections.to_csv(out / 'design_projections.csv', index=False)
        persist.to_csv(out / 'persistence.csv', index=False)
        moved.to_csv(out / 'transfer.csv', index=False)
        selected.to_csv(out / 'selections.csv', index=False)
        generation.to_csv(out / 'generation.csv', index=False)
        write_json(out / 'audit.json', {'source_run': source_audit, 'prediction_rows': len(predictions),
                   'metric_rows_regenerated': checked, 'selected_models': len(selections),
                   'upper_C_selections': int((selected.C == max(contract['C'])).sum()),
                   'integration': json.loads((source / 'integration.json').read_text(encoding='utf-8')),
                   'scientific_bank_opened': False,
                   'scope': 'Exposed development sensitivity; not V03 freeze, confirmation or independent A03 review.'})
        (out / 'report.md').write_text(report(contract, generation, selected, contrasts, components, projections, persist, moved,
                                              args.run_id, source.name), encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('audit.json', 'bank_contrasts.csv', 'design_projections.csv', 'generation.csv', 'persistence.csv', 'report.md',
             'selections.csv', 'transfer.csv', 'variance_components.csv')
    provenance = {'run_id': args.run_id, 'source_runs': [source.name], 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


def report(contract, generation, selected, contrasts, components, projections, persist, moved, run_id, source) -> str:
    gen = (generation.groupby(['configuration', 'role']).agg(banks=('bank', 'size'), scenarios=('scenarios', 'sum'),
                                                              positives=('positives', 'sum')).reset_index())
    gen['prevalence'] = gen.positives / gen.scenarios
    upper = (selected.assign(upper=selected.C == max(contract['C'])).groupby(['configuration', 'arm']).upper.sum()
             .unstack(fill_value=0).reset_index())
    native = contrasts[contrasts.training_configuration == contrasts.evaluation_configuration]
    p1 = native[native.id == 'P1'][['training_configuration', 'training_bank', 'mean', 'se', 'lower95', 'upper95',
                                    'reuse_new_misses_arm', 'positives']]
    pers = persist[persist.id.isin(['P1', 'S1', 'S2', 'S3', 'S5', 'S6'])]
    iso = contract['transfer_source']
    proj = projections[projections.id.isin(['P1', 'S2', 'S3', 'S6'])]
    return f'''# V02 development sensitivity and independent training banks

Date: 10 October 2026. Source `{source}`; summary `{run_id}`. **Exposed development
evidence generated under the committed [sensitivity contract](../../execution/sensitivity_contract.md).
The candidate scientific configuration and the scientific reservation were not
generated.** Decisions that use this evidence are recorded in
`docs/research/execution/analysis_specification.md`.

## Banks

Fresh development banks per configuration (training banks of
{contract['training_scenarios']:,}, evaluation banks of {contract['evaluation_scenarios']:,} scenarios). The enriched
synthetic prevalence is not operational prevalence.

{table(gen, ['configuration', 'role', 'banks', 'scenarios', 'positives', 'prevalence'])}

Selections at the upper C boundary, by configuration and arm (two banks per
configuration; six for `{iso}`):

{table(upper, list(upper.columns))}

## P1 on every independent training bank

P1 is the degradation of singleton relative to latest_metadata at 90% overlap,
evaluated on the configuration's own evaluation bank. Intervals are t-intervals
over evaluation scenarios, conditional on the fitted bank. `reuse_new_misses_arm`
counts positives missed under overlap but reviewed without reuse.

{table(p1, list(p1.columns))}

## Persistence across configurations

Counts are training banks; margin {MARGIN} nats. Descriptive development
evidence: each configuration has only two banks except `{iso}`.

{table(pers, ['training_configuration', 'id', 'estimand', 'banks', 'mean_min', 'mean_max', 'lower_above_margin', 'lower_above_zero', 'upper_below_zero', 'positives'])}

## Training-bank versus evaluation variance (`{iso}`, six independent banks)

Two-way random-effects decomposition of per-scenario contrasts (scenarios x
banks, one value per cell). `var_bank` is variation of the bank-level contrast
across independently generated training banks beyond scenario noise;
`var_interaction` is scenario-specific disagreement between banks.

{table(components, ['id', 'grand_mean', 'bank_means_sd', 'var_scenario', 'var_bank', 'var_interaction', 'bank_truncated', 'evaluation_se_one_bank_n2000'])}

Projected standard error of the bank-averaged contrast for designs with K
independent training banks sharing n evaluation scenarios. `conditional_on_fit_se`
omits the bank component, so it describes those K fitted models rather than
the training procedure:

{table(proj, ['id', 'independent_training_banks', 'evaluation_scenarios', 'projected_se', 'projected_half_width', 'conditional_on_fit_se'])}

## Transfer of `{iso}`-trained models

Mean over the {iso} training banks of each contrast on other configurations'
evaluation banks, next to models trained in that configuration.

{table(moved, ['evaluation_configuration', 'id', 'transfer_mean', 'transfer_min', 'transfer_max', 'native_mean'])}

## Limits

- Static two-dimensional encounter-plane model; no orbital dynamics or OD
  validation. Configurations are design stresses, not measured sensor behavior.
- Two training banks per non-baseline configuration show direction and rough
  size only. Six banks give a coarse bank-variance estimate; negative moment
  estimates are truncated at zero and flagged.
- All banks here are exposed development data used to choose the V03 design.
- Same-workflow analysis, not independent A03 review.
'''


if __name__ == '__main__':
    main()
