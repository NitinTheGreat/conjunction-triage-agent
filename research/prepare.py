"""Offline crosswalk and paper data extraction. Run with python -m research.prepare."""
from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from core.features_causal import build_dataset_causal, FEATURE_COLUMNS_CAUSAL
from research.artifacts import ROOT, Run, sql_path, write_json, write_table
from research.data import RAW_FIELDS, lineage, visible_records

FILES = {'raw': 'raw_data_2015-2019.gz', 'train': 'train_data.csv',
         'test': 'test_data.csv', 'private': 'test_data_private.csv'}
FP_FIELDS = ['time_to_tca', 'mission_id', 'risk', 'max_risk_estimate', 'max_risk_scaling',
             'miss_distance', 'relative_speed', 't_sigma_r', 'c_sigma_r']


def equivalent(column: str, split: str) -> str:
    a = f's."{"true_risk" if split == "private" and column == "risk" else column}"'
    b = f'r."{column}"'
    x, y = f'TRY_CAST({a} AS DOUBLE)', f'TRY_CAST({b} AS DOUBLE)'
    return f'''coalesce(CASE WHEN {a} IS NULL AND {b} IS NULL THEN true
        WHEN {x} IS NOT NULL AND {y} IS NOT NULL THEN
          (isnan({x}) AND isnan({y})) OR {x}={y} OR
          abs({x}-{y}) <= 1e-10+1e-8*greatest(abs({x}),abs({y}))
        ELSE trim({a})=trim({b}) END,false)'''


def crosswalk(con, run):
    summary = {'rtol': 1e-8, 'atol': 1e-10, 'event_mapping': 'nine-field fingerprint followed by unique event mapping and time join', 'splits': {}}
    for name, filename in FILES.items():
        path = ROOT / 'dataset/kelvins' / filename
        con.execute(f'''CREATE VIEW {name}_src AS SELECT row_number() OVER () AS row_id,*
            FROM read_csv('{sql_path(path)}',header=true,all_varchar=true,parallel=false)''')
        cols = [('true_risk' if f == 'risk' and name == 'private' else f) for f in FP_FIELDS]
        fp = ','.join(f"printf('%.10g',TRY_CAST(\"{f}\" AS DOUBLE))" for f in cols)
        con.execute(f'''CREATE TABLE {name}_keys AS SELECT row_id,cast(event_id AS BIGINT) event_id,
            cast(time_to_tca AS DOUBLE) tau,hash({fp}) fp FROM {name}_src''')
    crosswalks = []
    for name in ('train', 'test', 'private'):
        print(f'Crosswalk {name}: event mapping and full-column comparison', flush=True)
        con.execute(f'''CREATE TABLE event_map AS SELECT s.event_id source_event_id,
            min(r.event_id) raw_event_id,count(distinct r.event_id) raw_candidate_events
            FROM {name}_keys s JOIN raw_keys r USING(fp) GROUP BY s.event_id''')
        con.execute(f'''CREATE TABLE pairs AS SELECT s.row_id source_row_id,s.event_id source_event_id,
            m.raw_event_id,m.raw_candidate_events,min(r.row_id) raw_row_id,count(r.row_id) row_candidates
            FROM {name}_keys s LEFT JOIN event_map m ON s.event_id=m.source_event_id
            LEFT JOIN raw_keys r ON m.raw_candidate_events=1 AND r.event_id=m.raw_event_id
              AND abs(s.tau-r.tau)<=1e-10+1e-8*greatest(abs(s.tau),abs(r.tau))
            GROUP BY s.row_id,s.event_id,m.raw_event_id,m.raw_candidate_events''')
        columns = [x[0] for x in con.execute('DESCRIBE raw_src').fetchall() if x[0] not in ('row_id', 'event_id')]
        expressions = [f'CASE WHEN {equivalent(c, name)} THEN 0 ELSE 1 END' for c in columns]
        joined = f'''FROM pairs p JOIN {name}_src s ON p.source_row_id=s.row_id
                      JOIN raw_src r ON p.raw_row_id=r.row_id WHERE p.row_candidates=1 AND p.raw_candidate_events=1'''
        counts = con.execute('SELECT '+','.join(f'sum({e})' for e in expressions)+' '+joined).fetchone()
        con.execute('CREATE TABLE differences AS SELECT p.source_row_id,('+ '+'.join(expressions)+') differing_columns '+joined)
        result = con.execute('''SELECT p.*,d.differing_columns FROM pairs p LEFT JOIN differences d USING(source_row_id)
            ORDER BY source_row_id''').fetchdf()
        result['split'] = name
        result['status'] = np.where((result.row_candidates == 1) & (result.raw_candidate_events == 1),
                                    np.where(result.differing_columns.fillna(-1) == 0, 'matched_all_columns', 'column_difference'), 'unresolved')
        counts_by_status = {str(k): int(v) for k, v in result.status.value_counts().items()}
        summary['splits'][name] = {'rows': len(result), 'events': int(result.source_event_id.nunique()),
            'status': counts_by_status, 'column_differences': {c: int(n or 0) for c, n in zip(columns, counts)},
            'compared_columns': len(columns), 'unresolved_rows': result.loc[result.status != 'matched_all_columns', 'source_row_id'].tolist()}
        crosswalks.append(result)
        for table in ('event_map', 'pairs', 'differences'):
            con.execute(f'DROP TABLE {table}')
    write_table(run.path / 'crosswalk.parquet', pd.concat(crosswalks, ignore_index=True))
    write_json(run.path / 'crosswalk_summary.json', summary)
    return summary


def extract(con, run):
    cohort_frames = []
    data_summary = {}
    for split in ('train', 'test'):
        features = build_dataset_causal(split)
        write_table(run.path / f'causal_features_{split}.parquet', features)
        # Source fields are retained only for messages surviving canonical ingestion.
        con.execute(f"CREATE VIEW canonical AS SELECT * FROM read_parquet('{sql_path(ROOT / 'processed/kelvins' / ('cdms_'+split+'.parquet'))}')")
        selected = ','.join(f'TRY_CAST(s."{c}" AS DOUBLE) AS "{c}"' for c in RAW_FIELDS)
        raw = con.execute(f'''SELECT '{split}:'||cast(s.event_id AS BIGINT)::VARCHAR series_id,{selected}
            FROM {split}_src s SEMI JOIN canonical c
                ON c.series_id='{split}:'||cast(s.event_id AS BIGINT)::VARCHAR
                AND c.time_to_tca_days=TRY_CAST(s.time_to_tca AS DOUBLE)
                AND c.risk_log10=TRY_CAST(s.risk AS DOUBLE)
            WHERE TRY_CAST(s.time_to_tca AS DOUBLE)>=2''').fetchdf()
        visible = visible_records(raw)
        write_table(run.path / f'visible_{split}.parquet', visible)
        cohort = con.execute(f'''SELECT '{split}:'||cast(event_id AS BIGINT)::VARCHAR series_id,
            count(*) raw_message_count,min(TRY_CAST(time_to_tca AS DOUBLE)) raw_last_days,
            max(TRY_CAST(time_to_tca AS DOUBLE)) raw_first_days,
            count(*) FILTER(WHERE TRY_CAST(time_to_tca AS DOUBLE)>=2) raw_visible_count
            FROM {split}_src GROUP BY event_id''').fetchdf()
        cohort['split'] = split
        cohort['retrospective_eligible'] = cohort.series_id.isin(features.series_id)
        cohort['prospectively_visible'] = cohort.series_id.isin(visible.series_id)
        cohort['selection_basis'] = 'processed retrospective benchmark; test preselected by provider'
        cohort['inclusion_reason'] = np.where(cohort.retrospective_eligible, 'historical_benchmark',
            np.where(cohort.prospectively_visible, 'visible_but_retrospectively_excluded', 'no_valid_visible_message'))
        series_path = ROOT / 'processed/kelvins' / f'series_{split}.parquet'
        labels = con.execute(f"SELECT series_id,final_risk_log10 AS final_risk FROM read_parquet('{sql_path(series_path)}')").fetchdf()
        cohort = cohort.merge(labels, on='series_id', how='left', validate='one_to_one')
        cohort['outcome_available'] = np.isfinite(cohort.final_risk)
        cohort['outcome_exposure'] = 'previously_exposed_retrospective'
        cohort_frames.append(cohort)
        assert set(features.series_id) <= set(visible.series_id)
        data_summary[split] = {'raw_events': len(cohort), 'eligible_events': len(features),
            'high_risk_eligible': int((features.final_risk >= -6).sum()),
            'visible_rows_after_canonical_ingestion': len(visible),
            'visible_rows_before_canonical_ingestion': int(cohort.raw_visible_count.sum()),
            'prospectively_visible_events': int(cohort.prospectively_visible.sum()),
            'missing_outcomes_visible': int((cohort.prospectively_visible & ~cohort.outcome_available).sum()),
            'missingness': {c: int(visible[c].isna().sum()) for c in RAW_FIELDS}}
        con.execute('DROP VIEW canonical')
    write_table(run.path / 'cohort.parquet', pd.concat(cohort_frames, ignore_index=True))
    descriptor = lineage()
    descriptor['causal_feature_columns'] = list(FEATURE_COLUMNS_CAUSAL)
    descriptor['causal_feature_source'] = 'core/features_causal.py; select only the named allowlist'
    write_json(run.path / 'feature_lineage.json', descriptor)
    write_json(run.path / 'data_summary.json', data_summary)
    return data_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--crosswalk-from', type=Path, help='Explicitly reuse validated crosswalk artifacts only; not a silent run resume')
    args = parser.parse_args()
    inputs = [ROOT / 'dataset/kelvins' / f for f in FILES.values()]
    inputs += sorted((ROOT / 'processed/kelvins').glob('*.parquet'))
    cfg = json.loads((ROOT / 'research/configs/development.json').read_text())
    if args.crosswalk_from:
        previous=json.loads((args.crosswalk_from/'manifest.json').read_text())
        from research.artifacts import sha256
        for source in inputs:
            if previous['inputs'].get(str(source)) != sha256(source):
                raise ValueError('Crosswalk input differs from recorded source: '+str(source))
        inputs += [args.crosswalk_from/name for name in ('crosswalk.parquet','crosswalk_summary.json','manifest.json')]
        cfg['crosswalk_reuse_from']=str(args.crosswalk_from)
    with Run(args.run_id, 'data_preparation', cfg, inputs) as run:
        run.access('Kelvins train/test/private/raw', 'crosswalk and retrospective cohort/extraction', 'all outcomes already exposed; no new holdout')
        with duckdb.connect() as con:
            con.execute("SET memory_limit='1GB'")
            con.execute('SET threads=2')
            con.execute(f"SET temp_directory='{sql_path(run.path / 'duckdb_tmp')}'")
            if args.crosswalk_from:
                for name in ('crosswalk.parquet','crosswalk_summary.json'):
                    shutil.copy2(args.crosswalk_from/name,run.path/name)
                for split in ('train','test'):
                    source=ROOT/'dataset/kelvins'/FILES[split]
                    con.execute(f"CREATE VIEW {split}_src AS SELECT * FROM read_csv('{sql_path(source)}',header=true,all_varchar=true,parallel=false)")
            else:
                crosswalk(con, run)
            summary = extract(con, run)
        print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
