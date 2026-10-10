"""A01 post-hoc addendum: OD-quality strata for the retrospective real-data contrasts.

Added after the main A01 outputs were visible, to cover the checklist's quality
sensitivity, which the A01 contract omitted. Exploratory and exposed: no
decision depends on it. Strata come from the latest visible message: missing
chaser OD fields, and tertiles of chaser weighted RMS with cut points fixed on
the training cohort and applied unchanged to the historical test split.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from research.artifacts import RUN_ROOT, Run, read_table, sha256, write_json
from research.summarize_pilot import audit_run, table
from research.summarize_real import paired
from research.track_r_analysis import studentized_bootstrap

CONTRASTS = (('R1', 'singleton', 'latest_metadata'), ('R2', 'grouped', 'singleton'), ('R3', 'latest_metadata', 'latest'))


def latest_quality(visible: pd.DataFrame) -> pd.DataFrame:
    """Chaser OD quality of each event's latest visible message (closest to TCA)."""
    latest = visible.sort_values(['series_id', 'time_to_tca'], ascending=[True, False]).groupby('series_id').tail(1)
    fields = ['c_weighted_rms', 'c_obs_used', 'c_actual_od_span']
    return pd.DataFrame({'series_id': latest.series_id.to_numpy(),
                         'chaser_fields_missing': latest[fields].isna().any(axis=1).to_numpy(),
                         'chaser_weighted_rms': latest.c_weighted_rms.to_numpy()})


def strata(quality: pd.DataFrame, cuts: np.ndarray) -> pd.Series:
    label = pd.Series('missing chaser OD fields', index=quality.series_id)
    present = ~quality.chaser_fields_missing.to_numpy()
    tertile = np.digitize(quality.chaser_weighted_rms.to_numpy()[present], cuts)
    label.iloc[np.flatnonzero(present)] = [f'rms tertile {t + 1}' for t in tertile]
    return label


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
    contract = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))['config']
    data = RUN_ROOT / contract['data_run']
    config = {'source': str(source), 'status': 'post hoc exploratory addendum; main A01 outputs were visible',
              'strata': 'latest visible message: missing chaser OD fields; tertiles of chaser weighted RMS (training cut points)',
              'bootstrap_resamples': 9999, 'bootstrap_seed': 20261110}
    with Run(args.run_id, 'real_quality_addendum', config, [source / 'manifest.json', data / 'visible_train.parquet', data / 'visible_test.parquet']) as run:
        quality = {s: latest_quality(read_table(data / f'visible_{s}.parquet')) for s in ('train', 'test')}
        train_present = quality['train'][~quality['train'].chaser_fields_missing]
        cuts = np.quantile(train_present.chaser_weighted_rms, [1 / 3, 2 / 3])
        rows = []
        for split, name in (('training_oof', 'oof_predictions'), ('historical_test', 'test_predictions')):
            frame = read_table(source / f'{name}.parquet').assign(mission_id=0)
            label = strata(quality['train' if split == 'training_oof' else 'test'], cuts)
            for cid, arm, comparator in CONTRASTS:
                d = paired(frame, arm, comparator)
                d['stratum'] = label.reindex(d.index).to_numpy()
                if d.stratum.isna().any():
                    raise ValueError('Every event needs a quality stratum')
                for stratum, g in d.groupby('stratum'):
                    row = {'split': split, 'id': cid, 'arm': arm, 'comparator': comparator, 'stratum': stratum,
                           'events': len(g), 'positives': int(g.y.sum()), 'mean': float(g.difference.mean())}
                    if len(g) >= 30 and g.difference.std() > 0:
                        b = studentized_bootstrap(g.difference.to_numpy(), 9999, 20261110)
                        row.update(lower=b['lower'], upper=b['upper'])
                    rows.append(row)
        result = pd.DataFrame(rows)
        result.to_csv(run.path / 'quality_strata.csv', index=False)
        write_json(run.path / 'audit.json', {'source_run': source_audit, 'rms_tertile_cuts': cuts.tolist(), 'rows': len(result),
                   'status': config['status']})
        (run.path / 'report.md').write_text(f'''# A01 addendum: OD-quality strata (post hoc, exploratory)

Run `{args.run_id}` from `{source.name}`. **Added after the main A01 results were
visible** to cover quality sensitivity, which the A01 contract omitted. Strata come
from each event's latest visible message:
- missing chaser OD fields;
- tertiles of chaser weighted RMS, with training cut points {cuts[0]:.4g} and
  {cuts[1]:.4g} applied unchanged to the test split.

Differences are clipped log loss per event; negative favours the first arm.
Intervals are event-level studentized bootstraps for strata of at least 30 events.
Exposed evidence; nothing here is confirmatory.

{table(result, [c for c in ['split', 'id', 'arm', 'comparator', 'stratum', 'events', 'positives', 'mean', 'lower', 'upper'] if c in result])}
''', encoding='utf-8')
    args.export.mkdir(parents=True, exist_ok=False)
    provenance = {'run_id': args.run_id, 'source_runs': [source.name], 'manifest_sha256': sha256(run.path / 'manifest.json'), 'artifacts': {}}
    for name in ('audit.json', 'quality_strata.csv', 'report.md'):
        shutil.copyfile(run.path / name, args.export / name)
        provenance['artifacts'][name] = sha256(run.path / name)
    write_json(args.export / 'provenance.json', provenance)
    print('EXPORTED', args.export, flush=True)


if __name__ == '__main__':
    main()
