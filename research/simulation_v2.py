"""Repair cadence controls on exposed pilot scenarios, without new holdout access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.artifacts import Run, read_table, sha256, write_json, write_table
from research.history import HistoryTransformer, PHI_NAMES, events_from_frame

CONDITIONS = ('no_reuse', 'overlap_50', 'overlap_90', 'solution_reissue',
              'exact_replay', 'new_information', 'burst_reissue')
CADENCE_SEED = 20261021


def cadence(identity: str) -> np.ndarray:
    """Publication times independent of outcomes, with unequal short clusters."""
    seed = int(hashlib.sha256(f'{CADENCE_SEED}/{identity}'.encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    return np.array([6., 5.90 + rng.uniform(-.02, .02),
                     5.75 + rng.uniform(-.02, .02), 3.5 + rng.uniform(-.2, .2),
                     2.09 + rng.uniform(-.02, .02), 2.])


def repair_bank(messages: pd.DataFrame, lineage: pd.DataFrame):
    """Keep numerical solutions/windows; change publication cadence and ages."""
    rows, memberships = [], []
    availability = np.r_[np.linspace(8., 6.1, 60), np.linspace(1., .1, 20)]
    originals = {}
    for (sid, condition), frame in messages.groupby(['series_id', 'condition'], sort=False):
        # Original exact replay contains three copies; use the no-reuse solutions.
        if condition != 'exact_replay':
            originals[sid, condition] = frame.sort_values('time_to_tca', ascending=False).to_dict('records')
    windows = {(r.series_id, r.condition, r.message_index): json.loads(r.observation_ids)
               for r in lineage.itertuples(index=False)}
    for sid in sorted(messages.series_id.unique()):
        times = cadence(sid)
        assert np.all(np.diff(times) < 0) and times[-1] == 2.
        for condition in CONDITIONS:
            source = 'no_reuse' if condition in ('exact_replay', 'burst_reissue') else condition
            solutions = originals[sid, source]
            assert len(solutions) == 6
            index = 0
            for j, (original, tau) in enumerate(zip(solutions, times)):
                repeats = (2, 1, 3, 1, 2, 1)[j] if condition == 'burst_reissue' else 1
                following = times[j + 1] if j < 5 else tau
                for repeat in range(repeats):
                    published = float(tau - (tau - following) * repeat / repeats)
                    ids = windows[sid, source, j]
                    assert np.all(availability[ids] >= published)
                    row = dict(original)
                    row.update(condition=condition, time_to_tca=published)
                    age = float(availability[ids].min() - published)
                    bounds = (0., 1.) if age < 1 else ((1., 2.) if age < 2 else (2., 180.))
                    for role in ('t', 'c'):
                        row[f'{role}_time_lastob_end'], row[f'{role}_time_lastob_start'] = bounds
                    rows.append(row)
                    memberships.append({'series_id': sid, 'condition': condition,
                        'message_index': index, 'source_solution_index': j,
                        'observation_ids': json.dumps(ids), 'available_at_tca_days': published,
                        'source_solution_id': ','.join(map(str, ids))})
                    if condition == 'exact_replay':
                        rows.extend([row.copy(), row.copy()])
                    index += 1
    return pd.DataFrame(rows), pd.DataFrame(memberships)


def control_diagnostics(messages, ids):
    """Test representations before performance; no labels used here."""
    result = {}
    d = len(PHI_NAMES)
    for condition in ('no_reuse', 'burst_reissue'):
        events = events_from_frame(messages[messages.condition == condition], ids)
        counts, designs = {}, {}
        for arm in ('singleton', 'fixed', 'thin', 'change'):
            transform = HistoryTransformer(arm).fit(events)
            X, owners, weights = transform.transform(events)
            assert np.allclose(np.bincount(owners, weights=weights), 1.)
            counts[arm] = {'partition_rows': len(X),
                           'group_or_retained_count_min': int(X[:, 3*d+1].min()),
                           'group_or_retained_count_max': int(X[:, 3*d+1].max())}
            designs[arm] = X, owners
        fixed, owners = designs['fixed']
        singleton = designs['singleton'][0]
        different_mean = np.any(np.abs(fixed[:, d:2*d] - singleton[owners, d:2*d]) > 1e-10, axis=1)
        counts['fixed']['events_with_nonuniform_mean'] = int(len(np.unique(owners[different_mean])))
        assert counts['fixed']['events_with_nonuniform_mean'] == len(ids)
        assert counts['thin']['group_or_retained_count_max'] < len(events[0].raw)
        if condition == 'burst_reissue':
            assert counts['change']['group_or_retained_count_max'] == 6 < len(events[0].raw)
        result[condition] = counts
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    manifest = json.loads((source/'manifest.json').read_text())
    if manifest['status'] != 'complete' or manifest['kind'] != 'simulation_software_pilot':
        raise ValueError('Expected completed original pilot generator')
    names = ['reservation.json']
    for bank in ('development', 'software', 'bias_stress'):
        names += [f'{kind}_{bank}{suffix}' for kind, suffix in
                  (('messages', '.parquet'), ('lineage', '.parquet'), ('cohort', '.parquet'), ('truth', '.npz'))]
    inputs = [source/'manifest.json', *[source/name for name in names]]
    for name in names:
        if sha256(source/name) != manifest['artifacts'][name]['sha256']:
            raise ValueError(f'Changed source artifact: {name}')
    config = {'cadence_seed': CADENCE_SEED, 'conditions': list(CONDITIONS),
        'source_run': str(source), 'latent_scenarios': 'existing exposed pilot banks; no new independent scenarios',
        'new_condition': 'burst_reissue repeats existing solutions at new publication times',
        'labels_and_unique_observations': 'unchanged from source; scientific reservation untouched'}
    with Run(args.run_id, 'simulation_cadence_repair', config, inputs) as run:
        counts = {}
        for bank in ('development', 'software', 'bias_stress'):
            run.access(bank, 'cadence repair of exposed scenarios', 'development only; scientific bank not accessed')
            cohort = read_table(source/f'cohort_{bank}.parquet')
            messages, lineage = repair_bank(read_table(source/f'messages_{bank}.parquet'),
                                             read_table(source/f'lineage_{bank}.parquet'))
            write_table(run.path/f'cohort_{bank}.parquet', cohort)
            write_table(run.path/f'messages_{bank}.parquet', messages)
            write_table(run.path/f'lineage_{bank}.parquet', lineage)
            # No duplicate binary truth archive: record its immutable source path/hash.
            counts[bank] = {'scenarios': len(cohort), 'positives': int((cohort.final_risk >= -6).sum()),
                            'messages': len(messages), 'latent_truth_source': str(source/f'truth_{bank}.npz')}
            if bank == 'development':
                diagnostics = control_diagnostics(messages, cohort.series_id.tolist()[:128])
                write_json(run.path/'control_diagnostics.json', diagnostics)
            print(bank, counts[bank], flush=True)
        write_json(run.path/'reservation.json', json.loads((source/'reservation.json').read_text()))
        write_json(run.path/'validation.json', {'banks': counts, 'scientific_bank_generated': False,
            'construction_checks': 'Irregular cadence, distinct time/thinning representations; change selection removes burst reissues.',
            'limitations': ['Static geometry', 'Exposed latent pilot scenarios', 'Unweighted enriched prevalence',
                           'Publication time changes; numerical state solutions remain fixed per observation window']})


if __name__ == '__main__':
    main()
