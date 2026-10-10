"""Frozen Track R scientific run (V04 entry point).

Phase 1 fits the frozen arms on K independent in-configuration training banks.
Phase 2 generates the evaluation bank, seals its labels in a separate file, and
writes label-free predictions plus model and prediction hashes before any
evaluation label is read. Phase 3 joins the sealed labels and applies the frozen
analysis. Reserved identities can be generated only through access derived from
a committed protocol with status `frozen` and a matching freeze record.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from research.artifacts import ROOT, Run, read_table, sha256, write_json, write_table
from research.metrics import loss
from research.precision_planning import contrast, discordance, paired_frames
from research.sensitivity_banks import ReservedAccess, cadence_bank, integration_check, noise_covariance
from research.sensitivity_campaign import evaluation_sets, fit_one, oracle_training_events
from research.simulation_regimes import scenario_folds, training_rows
from research.track_r_analysis import (bank_combined_interval, combined_one_sided_p, holm, primary_decision,
                                       reuse_miss_summary)

PROTOCOL = ROOT / 'docs/research/execution/track_r_protocol.json'
FREEZE = ROOT / 'docs/research/execution/track_r_freeze.json'
LATEST_ARMS = ('latest', 'latest_metadata')
REUSE_CONDITIONS = ('overlap_50', 'overlap_90', 'solution_reissue', 'burst_reissue')


def blob_id(path: Path) -> str:
    """Git blob id after the repository's line-ending normalization (portable across OSes)."""
    return subprocess.check_output(['git', 'hash-object', str(Path(path).resolve())], cwd=ROOT, text=True).strip()


def protocol_hash(path: Path) -> str:
    """Hash of the canonical JSON content, independent of line endings."""
    content = json.loads(Path(path).read_text(encoding='utf-8'))
    return hashlib.sha256(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def load_protocol(path: Path = PROTOCOL, freeze: Path = FREEZE, require_frozen: bool = True) -> dict:
    protocol = json.loads(Path(path).read_text(encoding='utf-8'))
    if require_frozen:
        if protocol.get('status') != 'frozen':
            raise ValueError('The scientific run requires a frozen protocol')
        for item in (path, freeze):
            committed = subprocess.check_output(['git', 'show', f'HEAD:{Path(item).resolve().relative_to(ROOT).as_posix()}'], cwd=ROOT)
            if json.loads(committed) != json.loads(Path(item).read_text(encoding='utf-8')):
                raise ValueError(f'{Path(item).name} differs from the committed version')
        record = json.loads(Path(freeze).read_text(encoding='utf-8'))
        if record.get('protocol_sha256') != protocol_hash(path):
            raise ValueError('Freeze record does not match the protocol')
        for module, expected in protocol['code_blob_ids'].items():
            if blob_id(ROOT / module) != expected:
                raise ValueError(f'Frozen code changed: {module}')
    noise_covariance(protocol['configuration']['eigenvalues'], protocol['configuration']['rotation_degrees'])
    banks = [b['bank'] for b in protocol['training_banks']] + [protocol['evaluation_bank']['bank']]
    if len(set(banks)) != len(banks) or len(protocol['training_banks']) != protocol['independent_training_banks']:
        raise ValueError('Bank plan is inconsistent')
    return protocol


def reserved_access(protocol: dict, path: Path) -> ReservedAccess:
    banks = {b['bank']: b['seed'] for b in protocol['training_banks']}
    banks[protocol['evaluation_bank']['bank']] = protocol['evaluation_bank']['seed']
    return ReservedAccess(protocol_hash(path), banks)


def matrices(protocol: dict):
    c = protocol['configuration']
    return noise_covariance(c['eigenvalues'], c['rotation_degrees']), np.eye(2) * c['shared_bias_variance']


def phase_train(protocol: dict, run: Run, access: ReservedAccess | None) -> dict:
    noise, bias = matrices(protocol)
    models, hashes = {}, {}
    for spec in protocol['training_banks']:
        run.access(spec['bank'], 'scientific training bank', 'training labels used for fitting only')
        cohort, messages, lineage = cadence_bank(protocol['training_scenarios'], spec['seed'], spec['bank'], noise, bias, access)
        frame, events, X = training_rows(cohort, messages, protocol['conditions'])
        splits = scenario_folds(frame, protocol['inner_folds'], spec['seed'])
        oracle = oracle_training_events(frame, cohort, messages, lineage)
        for arm in protocol['arms']:
            prefix = f"{spec['bank']}_{arm}"
            saved, selection = fit_one(arm, frame, events, X, oracle, splits, protocol, spec['seed'], run.path, prefix)
            write_json(run.path / f'selection_{prefix}.json', selection)
            files = sorted(run.path.glob(f'model_{prefix}.joblib')) or sorted(run.path.glob(f'model_{prefix}_c*_foldrefit.joblib'))
            if len(files) != 1:
                raise ValueError(f'Expected one refit model file for {prefix}')
            models[(spec['bank'], arm)] = saved
            hashes[prefix] = sha256(files[0])
            print('FITTED', prefix, 'C', selection['C'], flush=True)
    write_json(run.path / 'model_hashes.json', hashes)
    return models


def predict_unlabeled(saved: dict, sets: dict, arm: str) -> pd.DataFrame:
    """Calibrated forecasts and review flags from messages only; no label is available here."""
    rows = []
    for condition, (ids, events, oracle, X) in sets.items():
        q = saved['calibration'].predict(saved['model'].predict(X, oracle if arm == 'oracle_lineage_weight' else events))
        rows.append(pd.DataFrame({'series_id': ids.series_id.to_numpy(), 'arm': arm, 'condition': condition, 'q': q,
                                  'threshold95': saved['threshold95'], 'review95': q >= saved['threshold95']}))
    out = pd.concat(rows, ignore_index=True)
    pivot = out.pivot(index='series_id', columns='condition', values='q')
    np.testing.assert_allclose(pivot['no_reuse'], pivot['exact_replay'], rtol=0, atol=1e-12)
    if arm in LATEST_ARMS:
        for condition in REUSE_CONDITIONS:
            np.testing.assert_allclose(pivot['no_reuse'], pivot[condition], rtol=0, atol=1e-12)
    return out


def phase_predict(protocol: dict, run: Run, access: ReservedAccess | None, models: dict) -> None:
    noise, bias = matrices(protocol)
    spec = protocol['evaluation_bank']
    run.access(spec['bank'], 'scientific evaluation bank generation', 'labels sealed before any prediction')
    cohort, messages, lineage = cadence_bank(protocol['evaluation_scenarios'], spec['seed'], spec['bank'], noise, bias, access)
    write_table(run.path / 'sealed_labels.parquet', cohort[['series_id', 'final_risk']])
    ids = cohort[['series_id']].copy()
    del cohort
    sets = evaluation_sets(ids, messages, lineage)
    outputs = []
    for (bank, arm), saved in models.items():
        outputs.append(predict_unlabeled(saved, sets, arm).assign(training_bank=bank))
    predictions = pd.concat(outputs, ignore_index=True)
    write_table(run.path / 'predictions_unlabeled.parquet', predictions)
    write_json(run.path / 'phase2_commit.json', {
        'predictions_sha256': sha256(run.path / 'predictions_unlabeled.parquet'),
        'model_hashes_sha256': sha256(run.path / 'model_hashes.json'),
        'sealed_labels_sha256': sha256(run.path / 'sealed_labels.parquet'),
        'rows': len(predictions), 'labels_read': False})


def bank_matrix(labelled: pd.DataFrame, arm: str, comparator: str, condition: str, estimand: str):
    columns, misses = [], []
    for bank, group in labelled.groupby('training_bank', sort=True):
        pivots = paired_frames(group)
        columns.append(contrast(pivots, arm, comparator, condition, estimand).rename(bank))
        misses.append({'training_bank': bank, 'positives': int(pivots['y'].sum()),
                       **discordance(pivots, arm, comparator, condition)})
    frame = pd.concat(columns, axis=1)
    if frame.isna().any().any():
        raise ValueError('Banks do not share evaluation scenarios')
    return frame.to_numpy(), pd.DataFrame(misses)


def phase_analyse(protocol: dict, run: Run) -> dict:
    commit = json.loads((run.path / 'phase2_commit.json').read_text(encoding='utf-8'))
    if sha256(run.path / 'predictions_unlabeled.parquet') != commit['predictions_sha256']:
        raise ValueError('Predictions changed after the phase-2 commit')
    labels = read_table(run.path / 'sealed_labels.parquet')
    predictions = read_table(run.path / 'predictions_unlabeled.parquet')
    labelled = predictions.merge(labels.assign(y=(labels.final_risk >= -6).astype(int))[['series_id', 'y']],
                                 on='series_id', how='left', validate='many_to_one')
    if labelled.y.isna().any():
        raise ValueError('Missing sealed label')
    labelled['log_loss'] = loss(labelled.y.to_numpy(), labelled.q.to_numpy())
    write_table(run.path / 'predictions_labelled.parquet', labelled)
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
    family = analysis['confirmatory_secondary']
    rejected = holm({k: results[k]['p_value'] for k in family}, analysis['alpha'])
    for k in family:
        results[k]['holm_rejected'] = rejected[k]
    write_json(run.path / 'analysis.json', results)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    protocol = load_protocol()
    access = reserved_access(protocol, PROTOCOL)
    config = {'protocol_sha256': protocol_hash(PROTOCOL), 'freeze_sha256': sha256(FREEZE)}
    with Run(args.run_id, 'track_r_scientific', config, [PROTOCOL, FREEZE]) as run:
        noise, _ = matrices(protocol)
        write_json(run.path / 'integration.json', integration_check(noise, protocol['integration_seed']))
        models = phase_train(protocol, run, access)
        phase_predict(protocol, run, access, models)
        phase_analyse(protocol, run)
    print('COMPLETE', args.run_id, flush=True)


if __name__ == '__main__':
    main()
