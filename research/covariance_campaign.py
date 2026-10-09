"""Two covariance-proxy approximations on the immutable expanded-tuning design."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import zipfile

import joblib
import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json, write_table
from research.covariance_proxy import PROXY_ARMS, covariance_weights
from research.history import events_from_frame
from research.metrics import class_metrics
from research.simulation_regimes import ARMS, fit_arm, scenario_folds, training_rows
from research.summarize_pilot import audit_run
from research.tuning_stability import evaluate_arm, sample_scenarios


def legacy_history_matches(current, archived):
    """Require the old AST exactly after removing only the new-mode import/branch.

    This narrowly scoped compatibility gate prevents reusing saved controls after
    an unnoticed change to their feature calculations. It is not a generic source
    equivalence checker. PROXY_ARMS must also be disjoint from the archived arms.
    """
    tree = ast.parse(current)
    guard = ast.dump(ast.parse('self.mode in PROXY_ARMS', mode='eval').body)
    body = ast.dump(ast.parse('w, _ = covariance_weights(raw, self.mode)').body[0])

    class RemoveNewModes(ast.NodeTransformer):
        def visit_ImportFrom(self, node):
            if node.module == 'research.covariance_proxy':
                if [(n.name, n.asname) for n in node.names] == [('PROXY_ARMS', None), ('covariance_weights', None)]:
                    return None
            return node

        def visit_If(self, node):
            if (ast.dump(node.test) == guard and not node.orelse and len(node.body) == 1
                    and ast.dump(node.body[0]) == body):
                return None
            return self.generic_visit(node)

    stripped = RemoveNewModes().visit(tree)
    return ast.dump(stripped) == ast.dump(ast.parse(archived))


def check_reference(source, reference):
    audits = [audit_run(source), audit_run(reference)]
    data_manifest = json.loads((source/'manifest.json').read_text())
    ref_manifest = json.loads((reference/'manifest.json').read_text())
    assert data_manifest['kind'] == 'simulation_cadence_repair'
    assert ref_manifest['kind'] == 'expanded_tuning_sensitivity'
    assert set(PROXY_ARMS).isdisjoint(ref_manifest['config']['arms'])
    assert ref_manifest['config']['arms'] == list(ARMS)
    for path in source.glob('*.parquet'):
        assert ref_manifest['inputs'][str(path)] == sha256(path)
    unchanged = ('models.py', 'simulation_regimes.py', 'tuning_stability.py', 'data.py', 'metrics.py', 'evaluate.py')
    for name in unchanged:
        assert sha256(ROOT/'research'/name) == ref_manifest['code_sha256'][f'research/{name}'], name
    with zipfile.ZipFile(reference/'code_snapshot.zip') as archive:
        assert legacy_history_matches((ROOT/'research/history.py').read_text(),
                                      archive.read('research/history.py').decode('utf-8'))
    return ref_manifest['config'], {'source_runs': audits,
        'unchanged_shared_modules': list(unchanged), 'legacy_history_ast_unchanged': True,
        'same_cadence_inputs': True, 'reuse_scope': 'All nine archived control arms; no control refitting or new tuning.'}


def weight_diagnostics(banks):
    rows = []
    for (bank, condition), (_, events, _) in banks.items():
        for event in events:
            for arm in PROXY_ARMS:
                w, reason = covariance_weights(event.raw, arm)
                rows.append({'bank': bank, 'condition': condition, 'series_id': event.identity,
                    'arm': arm, 'reason': reason, 'messages': len(w), 'weight_min': float(w.min()),
                    'weight_max': float(w.max()), 'uniform_l1': float(np.abs(w-1/len(w)).sum()),
                    'inverse_weight_concentration': float(1/np.square(w).sum())})
    frame = pd.DataFrame(rows)
    summary = frame.groupby(['bank', 'condition', 'arm', 'reason'], as_index=False).agg(
        events=('series_id', 'size'), messages_min=('messages', 'min'), messages_max=('messages', 'max'),
        weight_min=('weight_min', 'min'), weight_max=('weight_max', 'max'),
        uniform_l1_max=('uniform_l1', 'max'),
        inverse_weight_concentration_min=('inverse_weight_concentration', 'min'),
        inverse_weight_concentration_max=('inverse_weight_concentration', 'max'))
    return frame, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    source, reference = args.source.resolve(), args.reference.resolve()
    config, compatibility = check_reference(source, reference)
    config = {**config, 'arms': list(PROXY_ARMS), 'reused_control_arms': list(ARMS),
        'reference': str(reference), 'source': str(source),
        'proxy': 'Aligned radial/tangential diagonal-volume approximation; log-linear trend versus direct inverse volume; not the published method or physical Pc.',
        'fallback': 'Uniform prefix weights for invalid sigma/variance/time, fewer than two times, or log-volume range <= 1e-12. Infinities in source records are rejected by canonicalize.',
        'concentration': 'Inverse sum of squared message weights is a descriptive weight statistic, not an independent sample count.'}
    inputs = [source/'manifest.json', reference/'manifest.json', *sorted(source.glob('*.parquet')),
              reference/'predictions.parquet', reference/'selections.json',
              *sorted(reference.glob('cohort_seed*.parquet')), *sorted(reference.glob('training_seed*.parquet')),
              *sorted(reference.glob('oof_seed*_no_reuse_only_singleton.parquet'))]
    with Run(args.run_id, 'covariance_proxy_development', config, inputs) as run:
        run.access('exposed development/software/bias banks', 'predeclared covariance approximations and direct-weighting ablation',
                   'same exposed scenarios and training subsets; scientific reservation unopened')
        write_json(run.path/'compatibility.json', compatibility)
        banks, messages = {}, {}
        for bank in ('development', 'software', 'bias_stress'):
            c = read_table(source/f'cohort_{bank}.parquet')
            messages[bank] = read_table(source/f'messages_{bank}.parquet')
            for condition, g in messages[bank].groupby('condition', sort=True):
                ev = events_from_frame(g, c.series_id.tolist())
                banks[bank, condition] = c, ev, np.array([[e.raw[-1, 0]] for e in ev])
        diagnostic_rows, diagnostics = weight_diagnostics(banks)
        write_table(run.path/'weight_diagnostics.parquet', diagnostic_rows)
        diagnostics.to_csv(run.path/'weight_diagnostics.csv', index=False)
        constant = diagnostic_rows.condition != 'new_information'
        assert (diagnostic_rows.loc[constant, 'reason'] == 'constant_volume').all()
        assert (diagnostic_rows.loc[constant, 'uniform_l1'] == 0).all()
        assert (diagnostic_rows.loc[~constant, 'reason'] == 'weighted').all()
        assert (diagnostic_rows.loc[~constant, 'uniform_l1'] > 1e-8).all()
        write_json(run.path/'preflight.json', {'complete_before_first_fit': True,
            'constant_covariance_conditions_uniform': True, 'new_information_weights_distinct': True,
            'event_mode_rows': len(diagnostic_rows), 'scientific_bank_opened': False})
        print('PREFLIGHT complete:', len(diagnostic_rows), 'event/mode diagnostics', flush=True)
        evaluation = {key: value for key, value in banks.items() if key[0] != 'development'}
        development = banks['development', 'no_reuse'][0]
        ref_predictions = read_table(reference/'predictions.parquet')
        ref_selections = json.loads((reference/'selections.json').read_text())
        predictions, metrics, selections, equivalences = [], [], [], []
        for trial in config['trials']:
            seed, fraction = trial['seed'], trial['fraction']
            cohort = read_table(reference/f'cohort_seed{seed}.parquet')
            pd.testing.assert_frame_equal(cohort, sample_scenarios(development, fraction, seed))
            for regime, conditions in config['regimes'].items():
                frame, events, X = training_rows(cohort, messages['development'], conditions)
                splits = scenario_folds(frame, config['inner_folds'], seed)
                membership = frame.assign(inner_fold=-1)
                for k, (_, valid) in enumerate(splits):
                    membership.loc[valid, 'inner_fold'] = k
                pd.testing.assert_frame_equal(membership, read_table(reference/f'training_seed{seed}_{regime}.parquet'))
                write_table(run.path/f'training_seed{seed}_{regime}.parquet', membership)
                for arm in PROXY_ARMS:
                    prefix = f'seed{seed}_{regime}_{arm}'
                    print('START', prefix, flush=True)
                    saved, selection, oof = fit_arm(frame, events, X, arm, splits, config['C'], seed,
                        max_iter=config['max_iter'], require_convergence=True)
                    selection.update(seed=seed, training_fraction=fraction, regime=regime)
                    output = evaluate_arm(saved, evaluation, seed, fraction, regime, arm)
                    if regime == 'no_reuse_only':
                        old = next(s for s in ref_selections if s['seed'] == seed and s['regime'] == regime and s['arm'] == 'singleton')
                        assert selection['C'] == old['C']
                        np.testing.assert_allclose(oof, read_table(reference/f'oof_seed{seed}_{regime}_singleton.parquet').raw_oof,
                                                   rtol=0, atol=1e-12)
                        assert abs(selection['threshold95']-old['threshold95']) < 1e-12
                        a = output[output.condition != 'new_information'].sort_values(['bank', 'condition', 'series_id'])
                        b = ref_predictions[(ref_predictions.seed == seed) & (ref_predictions.regime == regime) &
                            (ref_predictions.arm == 'singleton') & (ref_predictions.condition != 'new_information')].sort_values(['bank', 'condition', 'series_id'])
                        np.testing.assert_allclose(a.q, b.q, rtol=0, atol=1e-12)
                        equivalences.append({'seed': seed, 'arm': arm, 'singleton_oof_and_constant_condition_predictions': 'pass'})
                    selections.append(selection)
                    write_json(run.path/f'selection_{prefix}.json', selection)
                    write_table(run.path/f'oof_{prefix}.parquet', membership.assign(raw_oof=oof))
                    joblib.dump(saved, run.path/f'model_{prefix}.joblib')
                    write_table(run.path/f'predictions_{prefix}.parquet', output)
                    predictions.append(output)
                    for (bank, condition), g in output.groupby(['bank', 'condition']):
                        metrics.append({'seed': seed, 'training_fraction': fraction, 'regime': regime,
                            'arm': arm, 'bank': bank, 'condition': condition,
                            **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())})
                    write_json(run.path/'progress.json', {'completed_fits': len(selections),
                        'planned_fits': len(config['trials'])*len(config['regimes'])*len(PROXY_ARMS),
                                                         'last_completed': prefix})
                    print('DONE', prefix, 'C', selection['C'], 'seconds', round(selection['seconds'], 1), flush=True)
        write_table(run.path/'predictions.parquet', pd.concat(predictions, ignore_index=True))
        pd.DataFrame(metrics).to_csv(run.path/'metrics.csv', index=False)
        write_json(run.path/'selections.json', selections)
        write_json(run.path/'equivalence.json', equivalences)
        write_json(run.path/'completion.json', {'selected_models': len(selections),
            'prediction_rows': sum(len(p) for p in predictions), 'reused_control_models': len(ref_selections),
            'upper_grid_boundary': sum(s['C'] == max(config['C']) for s in selections),
            'no_reuse_singleton_equivalences': len(equivalences), 'scientific_bank_opened': False})
        print('Completed covariance-proxy campaign.', flush=True)


if __name__ == '__main__':
    main()
