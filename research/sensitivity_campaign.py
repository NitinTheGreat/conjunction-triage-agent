"""Development configuration sensitivity with independent training banks.

Generates fresh development banks under the committed contract (never the
scientific reservation), fits the matched-mixture arms behind the proposed
primary and secondary contrasts on each independent training bank, and
evaluates them on a fresh evaluation bank per configuration. Isotropic-trained
models are also evaluated on every other configuration. All outcomes here are
exposed development evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

import joblib
import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, sha256, write_json, write_table
from research.component_campaign import fit_component
from research.components import lineage_events
from research.data import visible_records
from research.history import events_from_frame
from research.metrics import class_metrics
from research.sensitivity_banks import cadence_bank, check_identity, integration_check, noise_covariance
from research.simulation_regimes import REGIMES, fit_arm, scenario_folds, training_rows
from research.tuning_stability import evaluate_arm

CONTRACT = ROOT / 'docs/research/execution/sensitivity_contract.json'
REGIME = 'matched_mixture'


def load_contract(path: Path = CONTRACT, require_committed: bool = True) -> dict:
    contract = json.loads(path.read_text(encoding='utf-8'))
    if require_committed:
        if contract['status'] != 'fixed_before_generation':
            raise ValueError('Campaign requires a fixed contract')
        committed = subprocess.check_output(['git', 'show', f'HEAD:{path.relative_to(ROOT).as_posix()}'], cwd=ROOT)
        if json.loads(committed) != contract:
            raise ValueError('Contract differs from the committed version')
    for name, spec in contract['configurations'].items():
        noise_covariance(spec['eigenvalues'], spec['rotation_degrees'])
    if contract['regime'] != REGIME or tuple(contract['conditions']) != REGIMES[REGIME]:
        raise ValueError('Contract regime/conditions disagree with the audited matched mixture')
    return contract


def bank_plan(contract: dict) -> list[dict]:
    """Every bank, seed and role, fixed before generation."""
    plan = []
    for index, (name, spec) in enumerate(contract['configurations'].items()):
        base = contract['seed_base'] + 10 * index
        plan.append({'configuration': name, 'role': 'evaluation', 'bank': f'sens_{name}_eval', 'seed': base,
                     'scenarios': contract['evaluation_scenarios']})
        for k in range(1, spec['training_banks'] + 1):
            plan.append({'configuration': name, 'role': 'training', 'bank': f'sens_{name}_t{k}', 'seed': base + k,
                         'scenarios': contract['training_scenarios']})
    seeds = [p['seed'] for p in plan]
    if len(set(seeds)) != len(seeds) or len({p['bank'] for p in plan}) != len(plan):
        raise ValueError('Bank seeds and identifiers must be unique')
    for p in plan:
        check_identity(p['bank'], p['seed'])
    return plan


def configuration_matrices(spec: dict):
    noise = noise_covariance(spec['eigenvalues'], spec['rotation_degrees'])
    bias = np.eye(2) * spec['shared_bias_variance']
    return noise, bias


def evaluation_sets(cohort, messages, lineage):
    """Per-condition visible events, oracle lineage events and latest-risk inputs."""
    sets = {}
    ids = cohort.series_id.tolist()
    for condition, group in messages.groupby('condition', sort=True):
        events = events_from_frame(visible_records(group), ids)
        oracle = lineage_events(group, lineage[lineage.condition == condition], ids)
        for a, b in zip(events, oracle):
            np.testing.assert_array_equal(a.raw, b.raw)
        sets[condition] = (cohort, events, oracle, np.array([[e.raw[-1, 0]] for e in events]))
    return sets


def oracle_training_events(frame, cohort, messages, lineage):
    lookup = {}
    ids = cohort.series_id.tolist()
    for condition in frame.condition.unique():
        group = messages[messages.condition == condition]
        lookup[condition] = {e.identity: e for e in lineage_events(group, lineage[lineage.condition == condition], ids)}
    return [lookup[r.condition][r.series_id] for r in frame.itertuples(index=False)]


def fit_one(arm, frame, events, X, oracle_events, splits, contract, seed, directory, prefix):
    grid = contract['C']
    if arm == 'oracle_lineage_weight':
        saved, selection = fit_component(frame, oracle_events, arm, splits, grid, seed, directory, prefix, contract['max_iter'])
        return saved, selection
    saved, selection, oof = fit_arm(frame, events, X, arm, splits, grid, seed, max_iter=contract['max_iter'], require_convergence=True)
    write_table(directory / f'oof_{prefix}.parquet', frame.assign(raw_oof=oof))
    joblib.dump(saved, directory / f'model_{prefix}.joblib')
    return saved, selection


def evaluate(saved, sets, arm, seed, training_configuration, training_bank, evaluation_configuration):
    banks = {(f'sens_{evaluation_configuration}_eval', c): (v[0], v[2] if arm == 'oracle_lineage_weight' else v[1], v[3])
             for c, v in sets.items()}
    output = evaluate_arm(saved, banks, seed, 1.0, REGIME, arm)
    return output.assign(training_configuration=training_configuration, training_bank=training_bank,
                         evaluation_configuration=evaluation_configuration)


def preflight(contract: dict, run: Run, scenarios: int, fit_scenarios: int) -> dict:
    """Integration checks per configuration plus generation and fitting timings."""
    result = {'integration': {}, 'generation_seconds_per_scenario': {}, 'fit_seconds': {}}
    for index, (name, spec) in enumerate(contract['configurations'].items()):
        noise, bias = configuration_matrices(spec)
        result['integration'][name] = integration_check(noise, contract['integration_seed_base'] + index)
        clock = time.perf_counter()
        cadence_bank(scenarios, contract['preflight_seed_base'] + index, f'sens_preflight_{name}', noise, bias)
        result['generation_seconds_per_scenario'][name] = (time.perf_counter() - clock) / scenarios
    noise, bias = configuration_matrices(contract['configurations']['iso'])
    cohort, messages, lineage = cadence_bank(fit_scenarios, contract['preflight_seed_base'] + 9, 'sens_preflight_fit', noise, bias)
    frame, events, X = training_rows(cohort, messages, contract['conditions'])
    splits = scenario_folds(frame, contract['inner_folds'], contract['preflight_seed_base'] + 9)
    oracle_events = oracle_training_events(frame, cohort, messages, lineage)
    directory = run.path / 'preflight_fits'
    directory.mkdir()
    for arm in contract['arms']:
        clock = time.perf_counter()
        fit_one(arm, frame, events, X, oracle_events, splits, contract, contract['preflight_seed_base'] + 9, directory, f'preflight_{arm}')
        result['fit_seconds'][arm] = time.perf_counter() - clock
    return result


def campaign(contract: dict, run: Run) -> None:
    plan = bank_plan(contract)
    write_json(run.path / 'bank_plan.json', plan)
    generated, integration = {}, {}
    for index, (name, spec) in enumerate(contract['configurations'].items()):
        noise, bias = configuration_matrices(spec)
        integration[name] = integration_check(noise, contract['integration_seed_base'] + index)
    write_json(run.path / 'integration.json', integration)
    counts = []
    for entry in plan:
        spec = contract['configurations'][entry['configuration']]
        noise, bias = configuration_matrices(spec)
        run.access(entry['bank'], 'fresh development bank for configuration/training-bank sensitivity',
                   'development outcomes exposed by design; scientific reservation not generated')
        clock = time.perf_counter()
        cohort, messages, lineage = cadence_bank(entry['scenarios'], entry['seed'], entry['bank'], noise, bias)
        for kind, frame in (('cohort', cohort), ('messages', messages), ('lineage', lineage)):
            write_table(run.path / f"{kind}_{entry['bank']}.parquet", frame)
        generated[entry['bank']] = (cohort, messages, lineage)
        counts.append({**entry, 'positives': int((cohort.final_risk >= -6).sum()), 'messages': len(messages),
                       'seconds': time.perf_counter() - clock})
        print('GENERATED', entry['bank'], counts[-1]['positives'], flush=True)
    write_json(run.path / 'generation.json', counts)
    evaluation = {name: evaluation_sets(*generated[f'sens_{name}_eval']) for name in contract['configurations']}
    outputs, selections, metrics = [], [], []
    planned = sum(1 for p in plan if p['role'] == 'training') * len(contract['arms'])
    for entry in [p for p in plan if p['role'] == 'training']:
        cohort, messages, lineage = generated[entry['bank']]
        frame, events, X = training_rows(cohort, messages, contract['conditions'])
        splits = scenario_folds(frame, contract['inner_folds'], entry['seed'])
        membership = frame.assign(inner_fold=-1)
        for k, (_, valid) in enumerate(splits):
            membership.loc[valid, 'inner_fold'] = k
        write_table(run.path / f"training_{entry['bank']}.parquet", membership)
        oracle_events = oracle_training_events(frame, cohort, messages, lineage)
        targets = list(contract['configurations']) if entry['configuration'] == contract['transfer_source'] else [entry['configuration']]
        for arm in contract['arms']:
            prefix = f"{entry['bank']}_{arm}"
            print('START', prefix, flush=True)
            saved, selection = fit_one(arm, frame, events, X, oracle_events, splits, contract, entry['seed'], run.path, prefix)
            selection.update(seed=entry['seed'], configuration=entry['configuration'], training_bank=entry['bank'], regime=REGIME)
            selections.append(selection)
            write_json(run.path / f'selection_{prefix}.json', selection)
            for target in targets:
                output = evaluate(saved, evaluation[target], arm, entry['seed'], entry['configuration'], entry['bank'], target)
                write_table(run.path / f'predictions_{prefix}_on_{target}.parquet', output)
                outputs.append(output)
                for (bank, condition), g in output.groupby(['bank', 'condition']):
                    metrics.append({'training_configuration': entry['configuration'], 'training_bank': entry['bank'],
                                    'evaluation_configuration': target, 'arm': arm, 'condition': condition,
                                    **class_metrics(g.y.to_numpy(), g.q.to_numpy(), g.review95.to_numpy())})
            write_json(run.path / 'progress.json', {'completed_models': len(selections), 'planned_models': planned,
                                                    'last_completed': prefix})
            print('DONE', prefix, 'C', selection['C'], 'seconds', round(selection['seconds'], 1), flush=True)
    predictions = pd.concat(outputs, ignore_index=True)
    if len(predictions) != contract['planned_prediction_rows'] or len(selections) != planned:
        raise ValueError('Completed outputs disagree with the contract plan')
    write_table(run.path / 'predictions.parquet', predictions)
    pd.DataFrame(metrics).to_csv(run.path / 'metrics.csv', index=False)
    write_json(run.path / 'selections.json', selections)
    write_json(run.path / 'completion.json', {'selected_models': len(selections), 'prediction_rows': len(predictions),
               'training_banks': sum(1 for p in plan if p['role'] == 'training'),
               'upper_C_selections': sum(s['C'] == max(contract['C']) for s in selections),
               'scientific_bank_opened': False})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--preflight', action='store_true', help='timing/integration preflight from a draft contract')
    parser.add_argument('--preflight-scenarios', type=int, default=40)
    parser.add_argument('--preflight-fit-scenarios', type=int, default=300)
    args = parser.parse_args()
    contract = load_contract(require_committed=not args.preflight)
    kind = 'sensitivity_preflight' if args.preflight else 'sensitivity_development'
    config = {**contract, 'contract_sha256': sha256(CONTRACT)}
    if not args.preflight:
        config['contract_commit'] = subprocess.check_output(['git', 'log', '-1', '--format=%H', '--', str(CONTRACT)], cwd=ROOT, text=True).strip()
    with Run(args.run_id, kind, config, [CONTRACT]) as run:
        if args.preflight:
            write_json(run.path / 'preflight.json', preflight(contract, run, args.preflight_scenarios, args.preflight_fit_scenarios))
        else:
            campaign(contract, run)
    print('COMPLETE', args.run_id, flush=True)


if __name__ == '__main__':
    main()
