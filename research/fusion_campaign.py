"""Exposed-bank Gaussian state diagnostics with visible-only observation oracles."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json, write_table
from research.data import RAW_FIELDS
from research.history import canonicalize
from research.simulation import NOISE_VARIANCE, disk_probability, posterior
from research.state_fusion import FUSION_ARMS, fuse_gaussians, oracle_estimates, state_metrics, visible_union
from research.summarize_pilot import audit_run

BANKS = ('development', 'software', 'bias_stress')
AVAILABILITY = np.r_[np.linspace(8., 6.1, 60), np.linspace(1., .1, 20)]


def reconstruct_bank(cohort, messages, lineage, states, observations, bank):
    """Validate every released message before calculating any fused-state outcome."""
    if (not cohort.series_id.is_unique or states.shape != (len(cohort), 2) or
            observations.shape != (len(cohort), 80, 2)):
        raise ValueError('Invalid truth/cohort mapping or shapes')
    if not np.isfinite(states).all():
        raise ValueError('Nonfinite latent state')
    grouped_messages = dict(tuple(messages.groupby(['series_id', 'condition'], sort=False)))
    grouped_lineage = dict(tuple(lineage.groupby(['series_id', 'condition'], sort=False)))
    assert set(grouped_messages) == set(grouped_lineage)
    conditions = sorted(messages.condition.unique())
    assert set(grouped_messages) == {(sid, condition) for sid in cohort.series_id for condition in conditions}
    rows, prepared = [], []
    for i, sid in enumerate(cohort.series_id):
        cache = {}
        for condition in conditions:
            raw = canonicalize(grouped_messages[sid, condition][list(RAW_FIELDS)].to_numpy(float))
            lin = grouped_lineage[sid, condition].sort_values('message_index')
            if len(raw) != len(lin) or not np.array_equal(lin.message_index, np.arange(len(raw))):
                raise ValueError('Canonical message/lineage cardinality mismatch')
            means, covariances, windows = [], [], []
            for j, entry in enumerate(lin.itertuples(index=False)):
                ids = json.loads(entry.observation_ids)
                visible_union([ids])  # Reject noninteger, repeated, negative and later IDs.
                tau = raw[j, RAW_FIELDS.index('time_to_tca')]
                if tau < 2 or not np.isclose(tau, entry.available_at_tca_days, rtol=0, atol=1e-12):
                    raise ValueError('Publication/decision boundary disagreement')
                if not np.all(AVAILABILITY[ids] >= tau):
                    raise ValueError('Observation unavailable at publication')
                assert entry.source_solution_id == ','.join(map(str, ids))
                key = tuple(ids)
                if key not in cache:
                    mu, covariance = posterior(observations[i, ids], np.eye(2)*NOISE_VARIANCE)
                    risk = float(np.log10(max(disk_probability(mu, covariance), 1e-30)))
                    cache[key] = mu, covariance, risk
                mu, covariance, risk = cache[key]
                np.testing.assert_allclose(raw[j, RAW_FIELDS.index('risk')], risk, rtol=0, atol=1e-11)
                np.testing.assert_allclose(raw[j, RAW_FIELDS.index('miss_distance')], np.linalg.norm(mu), rtol=0, atol=1e-12)
                for role in ('t', 'c'):
                    for axis, expected in (('r', np.sqrt(covariance[0, 0]/2)),
                                           ('t', np.sqrt(covariance[1, 1]/2)), ('n', 0.)):
                        np.testing.assert_allclose(raw[j, RAW_FIELDS.index(f'{role}_sigma_{axis}')], expected, rtol=0, atol=1e-12)
                means.append(mu); covariances.append(covariance); windows.append(ids)
                rows.append({'bank': bank, 'series_id': sid, 'condition': condition, 'message_index': j,
                    'time_to_tca': float(tau), 'observations': len(ids), 'observation_max': int(max(ids)),
                    'mean_x': float(mu[0]), 'mean_y': float(mu[1]), 'cov_xx': float(covariance[0, 0]),
                    'cov_xy': float(covariance[0, 1]), 'cov_yy': float(covariance[1, 1]), 'recorded_logrisk': risk})
            prepared.append({'bank': bank, 'series_id': sid, 'condition': condition,
                'means': np.asarray(means), 'covariances': np.asarray(covariances), 'windows': windows,
                'observations': observations[i], 'truth': states[i],
                'shared_bias': bool(cohort.shared_bias.iloc[i])})
    return pd.DataFrame(rows), prepared


def evaluate_prepared(prepared):
    rows, ci_rows = [], []
    for item in prepared:
        estimates, ci = fuse_gaussians(item['means'], item['covariances'])
        oracle, ids = oracle_estimates(item['observations'], item['windows'], item['shared_bias'])
        estimates.update(oracle)
        identity = {k: item[k] for k in ('bank', 'series_id', 'condition')}
        ci_rows.append({**identity, 'method': ci['method'], 'weights': json.dumps(ci['weights']),
                        'optimality_gap': ci['optimality_gap'], 'messages': len(item['means']),
                        'visible_unique_observations': len(ids)})
        for arm in FUSION_ARMS:
            mu, P = estimates[arm]
            rows.append({**identity, 'arm': arm, 'messages': len(item['means']),
                'visible_unique_observations': len(ids), 'truth_x': float(item['truth'][0]),
                'truth_y': float(item['truth'][1]), 'mean_x': float(mu[0]), 'mean_y': float(mu[1]),
                'cov_xx': float(P[0, 0]), 'cov_xy': float(P[0, 1]), 'cov_yy': float(P[1, 1]),
                **state_metrics(mu, P, item['truth'])})
    estimates, diagnostics = pd.DataFrame(rows), pd.DataFrame(ci_rows)
    assert not estimates.duplicated(['bank', 'series_id', 'condition', 'arm']).any()
    check_identities(estimates)
    return estimates, diagnostics


def check_identities(estimates):
    columns = ['mean_x', 'mean_y', 'cov_xx', 'cov_xy', 'cov_yy', 'squared_error', 'quadratic_error']
    for bank, group in estimates.groupby('bank'):
        for arm, g in group.groupby('arm'):
            a = g[g.condition == 'no_reuse'].sort_values('series_id')
            b = g[g.condition == 'exact_replay'].sort_values('series_id')
            np.testing.assert_allclose(a[columns], b[columns], rtol=0, atol=1e-12)
        for condition, left, right in [('no_reuse', 'prior_once_product', 'oracle_unique'),
                ('new_information', 'latest', 'oracle_unique'),
                ('new_information', 'covariance_intersection', 'latest'),
                ('solution_reissue', 'covariance_intersection', 'latest')]:
            a = group[(group.condition == condition) & (group.arm == left)].sort_values('series_id')
            b = group[(group.condition == condition) & (group.arm == right)].sort_values('series_id')
            np.testing.assert_allclose(a[columns], b[columns], rtol=1e-11, atol=1e-11)
        if bank != 'bias_stress':
            a = group[group.arm == 'oracle_unique'].sort_values(['series_id', 'condition'])
            b = group[group.arm == 'oracle_bias_aware'].sort_values(['series_id', 'condition'])
            np.testing.assert_array_equal(a[columns], b[columns])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Cadence run')
    parser.add_argument('--truth-source', type=Path, required=True, help='Original exposed simulation run')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    source, truth_source = args.source.resolve(), args.truth_source.resolve()
    input_audits = [audit_run(source), audit_run(truth_source)]
    cadence_manifest = json.loads((source/'manifest.json').read_text())
    truth_manifest = json.loads((truth_source/'manifest.json').read_text())
    assert cadence_manifest['kind'] == 'simulation_cadence_repair'
    assert truth_manifest['kind'] == 'simulation_software_pilot'
    assert Path(cadence_manifest['config']['source_run']) == truth_source
    assert sha256(ROOT/'research/simulation.py') == truth_manifest['code_sha256']['research/simulation.py']
    names = [truth_source/'manifest.json', source/'manifest.json', *sorted(source.glob('*.parquet'))]
    for bank in BANKS:
        for name in (f'truth_{bank}.npz', f'cohort_{bank}.parquet'):
            path = truth_source/name
            assert cadence_manifest['inputs'][str(path)] == sha256(path)
            names.append(path)
    config = {'source': str(source), 'truth_source': str(truth_source), 'banks': list(BANKS),
        'conditions': cadence_manifest['config']['conditions'], 'arms': list(FUSION_ARMS),
        'ci': 'Basic precision CI; minimize logdet(P), equal identical-input/isotropic-minimum ties; otherwise SLSQP uniform start, ftol=1e-12, maxiter=1000, simplex gap <=1e-7. Fail on optimizer error.',
        'prior': 'N(0, 2.25 I), counted once only in prior_once_product and visible-union oracles',
        'oracle': 'Only unique visible IDs 0..59; known B=0.01 I used only by bias-aware oracle on bias_stress',
        'population': 'Unweighted enriched stress population; no Gaussian-prior coverage theorem',
        'endpoints': 'State squared error (m^2), error quadratic form, trace (m^2), 95% Gaussian-reference ellipse area (m^2) and inclusion',
        'ellipse_level': .95, 'bootstrap': {'replicates': 2000, 'seed': 20261040,
            'unit': 'latent scenario within bank; common resample across conditions/arms; marginal descriptive intervals'},
        'scientific_bank_generated': False}
    with Run(args.run_id, 'state_fusion_development', config, names) as run:
        run.access('three exposed simulation banks and visible lineage', 'state diagnostics, not final-class training',
                   'no new scenarios or reserved scientific access; later observations excluded from estimates')
        write_json(run.path/'input_audit.json', input_audits)
        prepared = []
        message_count = 0
        for bank in BANKS:
            c = read_table(source/f'cohort_{bank}.parquet')
            pd.testing.assert_frame_equal(c, read_table(truth_source/f'cohort_{bank}.parquet'))
            with np.load(truth_source/f'truth_{bank}.npz', allow_pickle=False) as truth:
                messages, items = reconstruct_bank(c, read_table(source/f'messages_{bank}.parquet'),
                    read_table(source/f'lineage_{bank}.parquet'), truth['states'], truth['observations'], bank)
            write_table(run.path/f'message_states_{bank}.parquet', messages)
            prepared.extend(items); message_count += len(messages)
            print('RECONSTRUCTED', bank, len(messages), 'canonical messages', flush=True)
        write_json(run.path/'preflight.json', {'all_messages_reconstructed_before_fusion': True,
            'canonical_messages': message_count, 'scenario_condition_cases': len(prepared),
            'max_permitted_observation_id': 59, 'risk_distance_sigmas_match': True})
        for bank in BANKS:
            results, ci = evaluate_prepared([p for p in prepared if p['bank'] == bank])
            write_table(run.path/f'estimates_{bank}.parquet', results)
            write_table(run.path/f'ci_{bank}.parquet', ci)
            print('FUSED', bank, len(results), 'scenario/condition/arm rows', flush=True)
        write_json(run.path/'completion.json', {'canonical_messages': message_count,
            'estimate_rows': len(prepared)*len(FUSION_ARMS), 'independent_scenarios_per_bank': len(prepared)//len(BANKS)//len(config['conditions']),
            'replay_and_oracle_identities': 'pass', 'scientific_bank_opened': False})
        print('Completed state-fusion development diagnostics.', flush=True)


if __name__ == '__main__':
    main()
