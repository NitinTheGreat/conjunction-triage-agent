"""Tuning-budget inventory and candidate-profile adequacy from completed runs.

Reads saved development artifacts only: no model is fitted and no scientific
scenario is generated. Grid-boundary selections are reported separately from
optimization failures. Step gains compare adjacent candidates on the selected
inner OOF objective; they are descriptive budget evidence, not proof that a
model family is optimized or that an extension would change evaluation results.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
import re
import shutil

import numpy as np
import pandas as pd

from research.artifacts import RUN_ROOT, Run, read_table, sha256, write_json
from research.history import PHI_NAMES
from research.metrics import loss
from research.summarize_pilot import audit_run, table

SOURCES = ('tuning_20261009_v1', 'covariance_20261009_v1', 'components_20261010_v1', 'sequence_20261010_v1')
BUNDLES = {'tuning_20261009_v1': 'tuning_2026-10-09', 'covariance_20261009_v1': 'covariance_2026-10-09',
           'components_20261010_v1': 'components_2026-10-10', 'sequence_20261010_v1': 'sequence_2026-10-10'}
TOLERANCES = (0.0005, 0.001, 0.0025, 0.005, 0.01)
SCORE_ATOL = 1e-12
SUMMARY_COLUMNS = 4 * len(PHI_NAMES) + 2
REPRESENTATION = {
    'latest': ('none', 'latest-message log-risk only'),
    'latest_metadata': ('none', 'latest-message fields plus per-field missingness'),
    'singleton': ('one partition', 'latest/mean/variance/span/count/missingness summary'),
    'grouped': ('<=8 label-free OD/time partitions; maximum score', 'summary per partition'),
    'fixed': ('<=8 time-gap-only partitions; maximum score', 'summary per partition'),
    'random': ('grouped family with hashed random membership', 'summary per partition'),
    'thin': ('one partition after >=6 h thinning', 'summary'),
    'change': ('one partition of OD/log-risk change messages', 'summary'),
    'ignore_updates': ('first visible message only', 'summary'),
    'covariance_trend': ('one partition; fitted log-volume trend weights', 'summary'),
    'covariance_direct': ('one partition; direct inverse-volume weights', 'summary'),
    'grouped_no_age': ('grouped partitions', 'summary without eight age bins'),
    'grouped_no_od_readout': ('grouped partitions (OD still forms groups)', 'summary without twelve OD fields'),
    'fixed_no_od': ('time-only partitions after canonicalization', 'summary without twelve OD fields'),
    'oracle_lineage_weight': ('one partition; privileged visible-lineage weights', 'summary'),
    'lstm_history': ('visible canonical message sequence', 'two-layer LSTM'),
    'lstm_latest': ('latest message only', 'two-layer LSTM'),
}


def logistic_profile(scores: dict, selected: float) -> dict:
    """Classify a C profile; ties select the smaller C, as in every campaign."""
    grid = sorted(float(c) for c in scores)
    values = np.array([float(scores[c]) for c in sorted(scores, key=float)])
    if len(grid) < 3 or not np.isfinite(values).all():
        raise ValueError('Expected at least three finite candidate scores')
    best = min(range(len(grid)), key=lambda k: (values[k], grid[k]))
    if grid[best] != float(selected):
        raise ValueError('Recorded selection disagrees with the minimum-score rule')
    neighbours = [values[k] - values[best] for k in (best - 1, best + 1) if 0 <= k < len(grid)]
    upper, previous = values[-2] - values[-1], values[-3] - values[-2]
    return {'setting': f'C={grid[best]:g}', 'boundary': 'upper' if best == len(grid) - 1 else 'lower' if best == 0 else 'interior',
            'best_loss': float(values[best]), 'adjacent_gap': float(min(neighbours)),
            'upper_step_gain': float(upper), 'previous_step_gain': float(previous),
            'step_ratio': float(upper / previous) if previous > 0 and upper > 0 else math.nan}


def lstm_profile(scores: list, hidden: int, epochs: int) -> dict:
    """Ties select the smaller width, then fewer epochs (sequence contract)."""
    frame = pd.DataFrame(scores).astype({'hidden': int, 'epochs': int, 'log_loss': float})
    if frame.duplicated(['hidden', 'epochs']).any() or not np.isfinite(frame.log_loss).all():
        raise ValueError('Expected unique finite neural candidates')
    best = frame.sort_values(['log_loss', 'hidden', 'epochs']).iloc[0]
    if (int(best.hidden), int(best.epochs)) != (int(hidden), int(epochs)):
        raise ValueError('Recorded selection disagrees with the minimum-score rule')
    widths, budgets = sorted(frame.hidden.unique()), sorted(frame.epochs.unique())
    score = frame.set_index(['hidden', 'epochs']).log_loss
    others = frame[(frame.hidden != hidden) | (frame.epochs != epochs)].log_loss
    return {'setting': f'h={hidden},e={epochs}',
            'boundary': ('upper' if epochs == budgets[-1] else 'lower' if epochs == budgets[0] else 'interior') + '_epochs;'
                        + ('upper' if hidden == widths[-1] else 'lower' if hidden == widths[0] else 'interior') + '_width',
            'best_loss': float(best.log_loss), 'adjacent_gap': float(others.min() - best.log_loss),
            'upper_step_gain': float(score[(hidden, budgets[-2])] - score[(hidden, budgets[-1])]),
            'width_step_gain': float(score[(widths[-2], epochs)] - score[(widths[-1], epochs)])}


def scenario_losses(frame: pd.DataFrame) -> pd.Series:
    """One objective unit per scenario, so their mean equals the weighted score."""
    weights = frame.groupby('series_id', sort=True).event_weight.sum()
    if not np.allclose(weights, 1.0, rtol=0, atol=1e-12):
        raise ValueError('Each scenario must carry total objective weight one')
    values = frame.event_weight.to_numpy() * loss(frame.y.to_numpy(), frame.raw_oof.to_numpy())
    return pd.Series(values, index=frame.series_id.to_numpy()).groupby(level=0, sort=True).sum()


def paired_step(worse_candidate: pd.Series, better_candidate: pd.Series) -> dict:
    """Scenario-paired gain of the second candidate; positive favors it."""
    if not worse_candidate.index.equals(better_candidate.index):
        raise ValueError('Candidates must share the same scenarios')
    gain = (worse_candidate - better_candidate).to_numpy()
    se = float(gain.std(ddof=1) / math.sqrt(len(gain)))
    return {'paired_gain': float(gain.mean()), 'paired_sd': float(gain.std(ddof=1)), 'paired_se': se,
            'paired_z': float(gain.mean() / se) if se > 0 else math.nan, 'paired_scenarios': len(gain)}


def fold_membership(membership: pd.DataFrame) -> pd.Series:
    """Map each scenario to its inner fold; every variant must share that fold."""
    folds = membership.groupby('series_id', sort=True).inner_fold
    if (folds.nunique() != 1).any() or (membership.inner_fold < 0).any():
        raise ValueError('Inner folds must keep each scenario whole')
    return folds.first()


def fold_scores(per_scenario: pd.Series, folds: pd.Series) -> pd.DataFrame:
    if not per_scenario.index.equals(folds.index):
        raise ValueError('Scenario losses and fold membership disagree')
    return (per_scenario.groupby(folds).agg(['size', 'mean']).rename(columns={'size': 'scenarios', 'mean': 'loss'})
            .rename_axis('fold').reset_index())


def folds_favoring_larger(smaller_budget: pd.Series, larger_budget: pd.Series, folds: pd.Series) -> int:
    gain = fold_scores(smaller_budget, folds).loss - fold_scores(larger_budget, folds).loss
    return int((gain > 0).sum())


def trace_summary(losses) -> dict:
    trace = np.asarray(losses, dtype=float)
    if trace.ndim != 1 or len(trace) < 11 or not np.isfinite(trace).all():
        raise ValueError('Expected at least eleven finite epoch losses')
    return {'final_training_loss': float(trace[-1]),
            'relative_drop_last10': float((trace[-11] - trace[-1]) / trace[-11]),
            'relative_drop_last5': float((trace[-6] - trace[-1]) / trace[-6]),
            'minimum_epoch': int(np.argmin(trace)) + 1, 'minimum_at_final_epoch': bool(np.argmin(trace) == len(trace) - 1)}


def profile_groups(profiles: pd.DataFrame) -> pd.Series:
    """Arms whose complete candidate profiles are bitwise identical in one trial/regime."""
    keys = profiles.sort_values('candidate').groupby(['seed', 'regime', 'arm']).loss.apply(tuple)
    groups = keys.reset_index().groupby(['seed', 'regime', 'loss']).arm.apply(lambda a: '+'.join(sorted(a)))
    lookup = {(s, r, a): g for (s, r, _), g in groups.items() for a in g.split('+')}
    return pd.Series({k: lookup[k] for k in keys.index})


def candidate_key(row) -> str:
    return f"C={row['C']:g}" if 'C' in row and pd.notna(row.get('C')) else f"h={int(row['hidden'])},e={int(row['epochs'])}"


FIT_NAME = re.compile(r'fit_seed(\d+)_(no_reuse_only|matched_mixture)_([a-z_]+?)_(?:c[0-9.e+-]+|h\d+_e\d+)_fold(\w+)\.json')


def load_run(path: Path):
    """Fit records omit trial seed/regime; their exclusive file names carry both."""
    manifest = json.loads((path / 'manifest.json').read_text(encoding='utf-8'))
    selections = json.loads((path / 'selections.json').read_text(encoding='utf-8'))
    completion = json.loads((path / 'completion.json').read_text(encoding='utf-8'))
    fits = []
    for name in sorted(glob.glob(str(path / 'fit_*.json'))):
        match = FIT_NAME.fullmatch(Path(name).name)
        record = json.loads(Path(name).read_text(encoding='utf-8'))
        if not match or match[3] != record['arm'] or match[4] != str(record['fold']):
            raise ValueError(f'Unexpected fit record name: {Path(name).name}')
        fits.append({**record, 'trial_seed': int(match[1]), 'regime': match[2]})
    return manifest, selections, completion, fits


def analyse(runs: dict[str, Path], bundles: Path | None = None):
    profiles, selections, steps, traces, fit_rows, inventory, checks, fold_rows = [], [], [], [], [], [], [], []
    for run_id, path in runs.items():
        manifest, chosen, completion, fits = load_run(path)
        neural = run_id.startswith('sequence')
        for record in fits:
            record = {**record, 'run_id': run_id, 'fold': str(record['fold'])}
            if record['status'] != 'complete':
                raise ValueError(f'Incomplete fit record in {run_id}')
            trace = record.pop('epoch_training_loss', None)
            if trace is not None:
                if len(trace) != record['epochs']:
                    raise ValueError('Trace length disagrees with epochs')
                batch = manifest['config']['batch_size']
                traces.append({**{k: record[k] for k in ('run_id', 'trial_seed', 'regime', 'arm', 'hidden', 'epochs', 'fold', 'fitting_rows')},
                               'steps_per_epoch': math.ceil(record['fitting_rows'] / batch),
                               'optimizer_steps': math.ceil(record['fitting_rows'] / batch) * record['epochs'], **trace_summary(trace)})
            fit_rows.append(record)
        for s in chosen:
            key = {'run_id': run_id, 'seed': s['seed'], 'regime': s['regime'], 'arm': s['arm']}
            if neural:
                result = lstm_profile(s['inner_scores'], s['hidden'], s['epochs'])
                candidates = [(f"h={c['hidden']},e={c['epochs']}", c['log_loss']) for c in s['inner_scores']]
            else:
                result = logistic_profile(s['inner_scores'], s['C'])
                candidates = [(f'C={float(c):g}', v) for c, v in s['inner_scores'].items()]
            profiles.extend({**key, 'candidate': c, 'loss': float(v), 'selected': c == result['setting']} for c, v in candidates)
            selections.append({**key, **result, 'seconds': s['seconds'],
                               'maximum_observed_iterations': s.get('maximum_observed_iterations', math.nan),
                               'training_scenarios': s['training_scenarios'], 'training_variant_rows': s['training_variant_rows']})
            membership = read_table(path / f"training_seed{s['seed']}_{s['regime']}.parquet")
            folds, rows = fold_membership(membership), membership[['series_id', 'condition']].to_numpy()
            recorded = dict(candidates)
            frame_path = path / f"candidates_seed{s['seed']}_{s['regime']}_{s['arm']}.parquet"
            if frame_path.exists():
                frame = read_table(frame_path)
                frame['candidate'] = frame.apply(candidate_key, axis=1)
                per = {}
                for c, g in frame.groupby('candidate', sort=False):
                    if not np.array_equal(g[['series_id', 'condition']].to_numpy(), rows):
                        raise ValueError('Candidate rows disagree with saved fold membership')
                    per[c] = scenario_losses(g)
                if set(per) != set(recorded):
                    raise ValueError('Candidate file and selection disagree')
                scope = 'all_candidates'
            else:
                # Older runs saved selected-candidate OOF only; reconcile that one.
                frame = read_table(path / f"oof_seed{s['seed']}_{s['regime']}_{s['arm']}.parquet")
                if not np.array_equal(frame[['series_id', 'condition', 'inner_fold']].to_numpy(),
                                      membership[['series_id', 'condition', 'inner_fold']].to_numpy()):
                    raise ValueError('Selected OOF rows disagree with saved fold membership')
                per, scope = {result['setting']: scenario_losses(frame)}, 'selected_only'
            worst = max(abs(per[c].mean() - recorded[c]) for c in per)
            if worst > SCORE_ATOL:
                raise ValueError(f'Saved candidate scores do not reconstruct: {worst}')
            checks.append({'run_id': run_id, 'seed': s['seed'], 'regime': s['regime'], 'arm': s['arm'], 'scope': scope,
                           'candidates': len(per), 'max_abs_score_difference': float(worst)})
            for c, values in per.items():
                fold_rows.extend({**key, 'candidate': c, 'selected': c == result['setting'], 'availability': scope, **r}
                                 for r in fold_scores(values, folds).to_dict('records'))
            selections[-1]['selected_fold_loss_range'] = float(np.ptp(fold_scores(per[result['setting']], folds).loss))
            if scope == 'all_candidates':
                if neural:
                    h, e = s['hidden'], s['epochs']
                    pairs = {'epoch_step': (f'h={h},e=20', f'h={h},e=60'), 'width_step': (f'h=16,e={e}', f'h=32,e={e}')}
                else:
                    pairs = {'upper_C_step': ('C=100', 'C=1000')}
                for name, (a, b) in pairs.items():
                    steps.append({**key, 'step': name, 'from': a, 'to': b, **paired_step(per[a], per[b]),
                                  'folds_favoring_larger': folds_favoring_larger(per[a], per[b], folds)})
        grid = (f"hidden {manifest['config']['hidden_widths']} x epochs {manifest['config']['epochs']}" if neural
                else f"C {manifest['config']['C']}")
        for arm in sorted({s['arm'] for s in chosen}):
            mine = [s for s in chosen if s['arm'] == arm]
            per_selection = (len(mine[0]['inner_scores']) * manifest['config']['inner_folds'] + 1)
            arm_fits = [f for f in fits if f['arm'] == arm]
            if arm_fits and len(arm_fits) != per_selection * len(mine):
                raise ValueError('Fit records disagree with the declared grid')
            columns = sorted({f['design_columns'] for f in arm_fits if 'design_columns' in f})
            parameters = sorted({f['parameters'] for f in arm_fits if 'parameters' in f})
            readout = (str(columns[0]) if len(columns) == 1 else '1' if arm == 'latest'
                       else str(2 * len(PHI_NAMES)) if arm == 'latest_metadata' else
                       f'parameters {parameters}' if parameters else str(SUMMARY_COLUMNS))
            settings = pd.Series([f"h={s['hidden']},e={s['epochs']}" if neural else f"C={s['C']:g}" for s in mine])
            inventory.append({'arm': arm, 'run_id': run_id, 'family': 'LSTM' if neural else 'logistic',
                              'partition_or_input': REPRESENTATION[arm][0], 'readout': REPRESENTATION[arm][1],
                              'readout_columns_or_parameters': readout, 'candidate_grid': grid,
                              'candidates_per_selection': len(mine[0]['inner_scores']), 'fits_per_selection': per_selection,
                              'fit_count_source': 'fit records' if arm_fits else 'derived from grid x folds + refit; complete stop-on-failure run',
                              'selections': len(mine), 'total_fits': per_selection * len(mine),
                              'selected_settings': '; '.join(f'{k}: {v}' for k, v in sorted(settings.value_counts().items())),
                              'failed_fits': sum(f['status'] != 'complete' for f in arm_fits),
                              'maximum_observed_iterations': max(s.get('maximum_observed_iterations', math.nan) for s in mine),
                              'fold_scores': ('all candidates' if (path / f"candidates_seed{mine[0]['seed']}_{mine[0]['regime']}_{arm}.parquet").exists()
                                              else 'selected candidate only'),
                              'selection_seconds_total': float(sum(s['seconds'] for s in mine))})
        checks.append({'run_id': run_id, 'completion': completion})
    profiles, selections = pd.DataFrame(profiles), pd.DataFrame(selections)
    groups = profile_groups(profiles)
    selections['identical_profile_arms'] = [groups[(s, r, a)] for s, r, a in selections[['seed', 'regime', 'arm']].itertuples(index=False)]
    if bundles is not None:
        for run_id in runs:
            exported = pd.read_csv(bundles / BUNDLES[run_id] / 'candidate_scores.csv')
            exported['candidate'] = exported.apply(candidate_key, axis=1)
            score = 'log_loss' if 'log_loss' in exported else 'inner_oof_log_loss'
            merged = profiles[profiles.run_id == run_id].merge(exported, on=['seed', 'regime', 'arm', 'candidate'], validate='one_to_one')
            if len(merged) != (profiles.run_id == run_id).sum() or not np.allclose(merged.loss, merged[score], rtol=0, atol=SCORE_ATOL):
                raise ValueError(f'Committed export disagrees with {run_id} selections')
            if not (merged.selected_x == merged.selected_y).all():
                raise ValueError('Committed export selection flags disagree')
    return {'profiles': profiles, 'selections': selections, 'steps': pd.DataFrame(steps), 'traces': pd.DataFrame(traces),
            'fits': pd.DataFrame(fit_rows), 'inventory': pd.DataFrame(inventory), 'checks': checks,
            'folds': pd.DataFrame(fold_rows)}


def summaries(result: dict) -> dict:
    sel = result['selections'].copy()
    sel['family'] = np.where(sel.run_id.str.startswith('sequence'), 'LSTM', 'logistic')
    sel['at_upper_budget'] = sel.boundary.str.startswith('upper')
    rows, tolerance = [], []
    for (family, regime), g in sel.groupby(['family', 'regime']):
        edge = g[g.at_upper_budget]
        distinct = g.drop_duplicates(['seed', 'identical_profile_arms'])
        rows.append({'family': family, 'regime': regime, 'selections': len(g), 'distinct_profiles': len(distinct),
                     'upper_budget_selections': len(edge), 'upper_budget_distinct': int(distinct.at_upper_budget.sum()),
                     'lower_C_selections': int((g.boundary == 'lower').sum()),
                     'upper_step_gain_median_all': float(g.upper_step_gain.median()),
                     'upper_step_gain_max_all': float(g.upper_step_gain.max()),
                     'upper_step_gain_median_at_edge': float(edge.upper_step_gain.median()) if len(edge) else math.nan,
                     'adjacent_gap_median': float(g.adjacent_gap.median()),
                     'selected_fold_loss_range_median': float(g.selected_fold_loss_range.median())})
        for tol in TOLERANCES:
            tolerance.append({'family': family, 'regime': regime, 'tolerance': tol, 'selections': len(g),
                              'edge_step_gain_above_tolerance': int((g.at_upper_budget & (g.upper_step_gain > tol)).sum()),
                              'distinct_edge_step_gain_above_tolerance': int((distinct.at_upper_budget & (distinct.upper_step_gain > tol)).sum()),
                              'adjacent_gap_below_tolerance': int((g.adjacent_gap < tol).sum())})
    steps = result['steps']
    paired = (steps.groupby(['run_id', 'regime', 'step']).agg(models=('paired_gain', 'size'), gain_median=('paired_gain', 'median'),
              gain_min=('paired_gain', 'min'), gain_max=('paired_gain', 'max'), se_median=('paired_se', 'median'),
              z_min=('paired_z', 'min'), z_max=('paired_z', 'max'), positive_gains=('paired_gain', lambda v: int((v > 0).sum())),
              larger_better_all_folds=('folds_favoring_larger', lambda v: int((v == 3).sum())),
              larger_better_no_fold=('folds_favoring_larger', lambda v: int((v == 0).sum())))
              .reset_index())
    trace = (result['traces'].groupby(['regime', 'arm', 'hidden', 'epochs'])
             .agg(fits=('fold', 'size'), steps_per_epoch_median=('steps_per_epoch', 'median'),
                  optimizer_steps_median=('optimizer_steps', 'median'), final_loss_median=('final_training_loss', 'median'),
                  relative_drop_last10_median=('relative_drop_last10', 'median'),
                  relative_drop_last10_max=('relative_drop_last10', 'max'),
                  minimum_at_final_epoch=('minimum_at_final_epoch', 'sum')).reset_index())
    return {'regime_summary': pd.DataFrame(rows), 'tolerance': pd.DataFrame(tolerance), 'paired_summary': paired, 'trace_summary': trace}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--export', type=Path, required=True)
    parser.add_argument('--bundles', type=Path, default=Path('docs/research/results'))
    args = parser.parse_args()
    if args.export.exists():
        raise FileExistsError(args.export)
    runs = {run_id: (RUN_ROOT / run_id).resolve() for run_id in SOURCES}
    audits = [audit_run(path) for path in runs.values()]
    with Run(args.run_id, 'tuning_adequacy_inventory', {'sources': list(SOURCES), 'tolerances': list(TOLERANCES),
             'score_atol': SCORE_ATOL, 'fitting': 'none'}, [p / 'manifest.json' for p in runs.values()]) as run:
        result = analyse(runs, args.bundles)
        extra = summaries(result)
        out = run.path
        result['inventory'].to_csv(out / 'inventory.csv', index=False)
        result['profiles'].to_csv(out / 'profiles.csv', index=False)
        result['selections'].to_csv(out / 'selection_adequacy.csv', index=False)
        result['steps'].to_csv(out / 'paired_steps.csv', index=False)
        result['traces'].to_csv(out / 'neural_traces.csv', index=False)
        extra['regime_summary'].to_csv(out / 'regime_summary.csv', index=False)
        extra['tolerance'].to_csv(out / 'tolerance_counts.csv', index=False)
        extra['paired_summary'].to_csv(out / 'paired_summary.csv', index=False)
        extra['trace_summary'].to_csv(out / 'trace_summary.csv', index=False)
        result['folds'].to_csv(out / 'fold_scores.csv', index=False)
        scored = [c for c in result['checks'] if 'scope' in c]
        write_json(out / 'audit.json', {'source_runs': audits, 'selections': len(result['selections']),
                   'candidate_profiles': len(result['profiles']), 'fit_records': len(result['fits']),
                   'fold_score_rows': len(result['folds']),
                   'reconstructed_all_candidate_models': sum(c['scope'] == 'all_candidates' for c in scored),
                   'reconstructed_selected_only_models': sum(c['scope'] == 'selected_only' for c in scored),
                   'max_abs_score_difference': max(c['max_abs_score_difference'] for c in scored),
                   'committed_exports_match': True, 'fitting_performed': False, 'scientific_bank_opened': False,
                   'scope': 'Same-workflow inventory of exposed development runs; not independent A03 review.'})
        (out / 'report.md').write_text(report(result, extra, args.run_id), encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    names = ('audit.json', 'fold_scores.csv', 'inventory.csv', 'neural_traces.csv', 'paired_steps.csv', 'paired_summary.csv', 'profiles.csv',
             'regime_summary.csv', 'report.md', 'selection_adequacy.csv', 'tolerance_counts.csv', 'trace_summary.csv')
    provenance = {'run_id': args.run_id, 'source_runs': list(SOURCES), 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in names:
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


def report(result: dict, extra: dict, run_id: str) -> str:
    inv, sel, fits = result['inventory'], result['selections'], result['fits']
    files = [c for c in result['checks'] if c.get('scope') == 'all_candidates']
    selected_only = [c for c in result['checks'] if c.get('scope') == 'selected_only']
    regime, tol, paired, trace = extra['regime_summary'], extra['tolerance'], extra['paired_summary'], extra['trace_summary']
    logistic = sel[~sel.run_id.str.startswith('sequence')]
    iterations = logistic.groupby('run_id').maximum_observed_iterations.max()
    seconds = inv.groupby('family').selection_seconds_total.sum()
    edge = lambda family, reg: regime[(regime.family == family) & (regime.regime == reg)].iloc[0]
    lm, ln = edge('logistic', 'matched_mixture'), edge('logistic', 'no_reuse_only')
    nm, nn = edge('LSTM', 'matched_mixture'), edge('LSTM', 'no_reuse_only')
    shown = tol[tol.tolerance.isin([0.0005, 0.001, 0.005, 0.01])]
    pc = paired[paired.run_id == 'components_20261010_v1']
    steps = result['traces'].groupby('regime').steps_per_epoch.agg(['min', 'max'])
    return f'''# V02 tuning adequacy: budget inventory and candidate profiles

Date: 10 October 2026. Run `{run_id}`. Sources: {', '.join(f'`{s}`' for s in SOURCES)}.
**Exposed development evidence only. No model was fitted, no evaluation forecast was
used, and the scientific bank was not generated.** The tuning decision that uses
this evidence is recorded separately in `docs/research/execution/tuning_decision.md`.

## Scope and checks

All four source runs pass manifest, input and archived-source checks before
reading. The inventory covers {len(inv)} class-forecast arms, {len(sel)} selected models,
{len(result['profiles'])} candidate scores and {len(fits)} per-fit records. Every recorded
selection is re-derived from its candidate scores with the campaign tie rule
(smaller C; for LSTM smaller width, then fewer epochs). For the {len(files)} models
whose runs saved every candidate's OOF predictions (component and sequence runs),
all candidate scores are recomputed from scenario-level predictions; for the other
{len(selected_only)}, the selected candidate's score is recomputed from its saved OOF predictions.
The largest absolute difference is {max(c['max_abs_score_difference'] for c in files + selected_only):.1e}. All candidate scores also
match the committed compact exports. Per-fold scores use each run's saved
whole-scenario inner-fold membership ({len(result['folds'])} rows in `fold_scores.csv`). The six
state-estimation arms have a different target and are excluded.

## Inventory

`readout` columns are the summary design width before imputer missingness
indicators. Each selection uses six candidates, three whole-scenario inner folds
and one refit (19 fits); every arm has four training trials x two regimes.

{table(inv, ['arm', 'family', 'partition_or_input', 'readout_columns_or_parameters', 'selected_settings', 'failed_fits', 'maximum_observed_iterations', 'fold_scores', 'selection_seconds_total'])}

Logistic selections used {seconds.get('logistic', 0) / 60:.1f} minutes of recorded selection time and the
LSTM selections {seconds.get('LSTM', 0) / 60:.1f} minutes, excluding evaluation and reconstruction.

## Grid limits are not optimization failures

No fit failed. The maximum observed L-BFGS iterations are
{', '.join(f'{r} {int(v)}' for r, v in iterations.items())} against a cap of 10,000, with strict convergence
required. A selection at C=1000 or at 60 epochs is therefore a limit of the declared
search, not a numerical failure, and a converged optimizer does not show that the
search was wide enough.

{table(regime, ['family', 'regime', 'selections', 'distinct_profiles', 'upper_budget_selections', 'upper_budget_distinct', 'upper_step_gain_median_at_edge', 'upper_step_gain_max_all', 'adjacent_gap_median', 'selected_fold_loss_range_median'])}

`upper_step_gain` is the inner-OOF loss of the second-largest budget minus that of
the largest (C=100 to 1000; for LSTM, 20 to 60 epochs at the selected width).
Positive values mean the objective was still improving at the edge. Under
no-reuse training several arms are bitwise identical models;
`distinct_profiles` removes those duplicates. `selected_fold_loss_range` is the
spread of the selected candidate's loss across its three inner folds, a scale for
fold heterogeneity rather than a confidence interval.

## Practical tolerance

The table counts edge selections whose last budget step improved the objective
by more than each tolerance, and selections whose nearest competing candidate is
within it (a flat profile that the development data do not resolve). Tolerances
are shown together because none was fixed before these development results
were seen.

{table(shown, ['family', 'regime', 'tolerance', 'selections', 'edge_step_gain_above_tolerance', 'distinct_edge_step_gain_above_tolerance', 'adjacent_gap_below_tolerance'])}

Matched-mixture logistic models: {int(lm.upper_budget_selections)}/{int(lm.selections)} selections reach C=1000,
with a largest last-step gain of {lm.upper_step_gain_max_all:.6f}. No-reuse logistic models:
{int(ln.upper_budget_selections)}/{int(ln.selections)} reach C=1000 ({int(ln.upper_budget_distinct)} distinct profiles), with a largest
last-step gain of {ln.upper_step_gain_max_all:.6f}. {int(nm.upper_budget_selections + nn.upper_budget_selections)}/{int(nm.selections + nn.selections)} LSTM selections use the maximum
60 epochs; median 20-to-60-epoch gains are {nm.upper_step_gain_median_at_edge:.6f} (matched) and
{nn.upper_step_gain_median_at_edge:.6f} (no reuse).

## Scenario-paired resolution

Only the component and sequence runs saved every candidate's OOF predictions.
Gains below are means over training scenarios of per-scenario objective
differences (each scenario carries weight one), with their paired standard
errors. Candidate predictions within one inner-fold design are correlated, so
these are descriptive resolution checks, not tests. The tuning and covariance
runs saved only selected-C OOF predictions; their step gains are aggregate only.

{table(paired, ['run_id', 'regime', 'step', 'models', 'gain_median', 'gain_min', 'gain_max', 'se_median', 'z_min', 'z_max', 'positive_gains', 'larger_better_all_folds', 'larger_better_no_fold'])}

`larger_better_all_folds` and `larger_better_no_fold` count models in which the
larger budget has lower loss in all three, or none, of the inner folds.

For the component arms under matched training, the C=100 to 1000 step favors
C=1000 in {int(pc[pc.regime == 'matched_mixture'].positive_gains.iloc[0])}/16 models; the largest paired z in its favor is
{pc[pc.regime == 'matched_mixture'].z_max.iloc[0]:.2f}. Under no-reuse training it favors C=1000 in
{int(pc[pc.regime == 'no_reuse_only'].positive_gains.iloc[0])}/16, with z up to {pc[pc.regime == 'no_reuse_only'].z_max.iloc[0]:.2f}.

## Neural training traces

Traces are minibatch training losses (dropout active), not validation curves.
With batch size 256, no-reuse fits take {steps.loc['no_reuse_only', 'min']}-{steps.loc['no_reuse_only', 'max']} minibatches per epoch
and matched fits {steps.loc['matched_mixture', 'min']}-{steps.loc['matched_mixture', 'max']}, so equal epochs are unequal optimizer
budgets across regimes.

{table(trace[trace.epochs == 60], ['regime', 'arm', 'hidden', 'fits', 'optimizer_steps_median', 'final_loss_median', 'relative_drop_last10_median', 'relative_drop_last10_max', 'minimum_at_final_epoch'])}

## What this evidence can and cannot establish

- It shows where the declared budgets bind on the training objective. It does
  not show that a wider grid or longer training would change evaluation-bank
  results, rankings or degradation contrasts; that requires new fits.
- Inner-OOF gains reuse one exposed development bank per trial; the three
  800-scenario subsets overlap the full-reference cohort.
- A flat profile within a tolerance is not evidence of equivalence for
  inference, and no tolerance here was prespecified.
- Neural traces lack validation curves; a training-loss plateau does not exclude
  further out-of-fold change, and continued decrease does not guarantee it.
- This is same-workflow artifact analysis, not independent A03 review.
'''


if __name__ == '__main__':
    main()
