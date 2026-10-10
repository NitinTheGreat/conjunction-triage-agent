"""Verify the A02 claim-evidence register against committed result bundles.

Each quantitative row names a bundle file, a pandas query, a column and a
statistic. The verifier recomputes the value from the committed export and
requires agreement within the row's tolerance. Pending rows (for example the V04
scientific result) must carry no value; documented rows must cite an existing file.
Sources are paths relative to the repository root.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

STATISTICS = {'value', 'min', 'max', 'mean', 'count', 'sum'}
EVIDENCE_TYPES = {'exposed development simulation', 'exposed retrospective real data', 'protocol', 'pending scientific evaluation',
                  'frozen scientific simulation'}


def recompute(row: pd.Series, results: Path) -> float:
    frame = pd.read_csv(results / row.source)
    selected = frame.query(row.selector) if isinstance(row.selector, str) and row.selector.strip() else frame
    if row.statistic == 'count':
        return float(len(selected))
    values = selected[row.column].astype(float)
    if values.empty:
        raise ValueError(f'{row.id}: selector matched no rows')
    if row.statistic == 'value':
        if len(values) != 1:
            raise ValueError(f'{row.id}: expected exactly one row, found {len(values)}')
        return float(values.iloc[0])
    return float(getattr(values, row.statistic)())


def verify(register: pd.DataFrame, results: Path) -> list[dict]:
    if register.id.duplicated().any():
        raise ValueError('Duplicate claim ids')
    outcomes = []
    for row in register.itertuples(index=False):
        if row.evidence_type not in EVIDENCE_TYPES:
            raise ValueError(f'{row.id}: unknown evidence type')
        if row.status == 'documented':
            if not (results / row.source).exists():
                raise ValueError(f'{row.id}: documented source is missing')
            outcomes.append({'id': row.id, 'status': 'documented'})
            continue
        if row.status == 'pending':
            if not (isinstance(row.source, float) and math.isnan(row.source)) or not math.isnan(row.expected):
                raise ValueError(f'{row.id}: a pending claim must not carry a source value')
            outcomes.append({'id': row.id, 'status': 'pending'})
            continue
        if row.statistic not in STATISTICS:
            raise ValueError(f'{row.id}: unknown statistic')
        actual = recompute(pd.Series(row._asdict()), results)
        if not abs(actual - row.expected) <= row.tolerance:
            raise ValueError(f'{row.id}: recomputed {actual} differs from {row.expected}')
        outcomes.append({'id': row.id, 'status': 'regenerated', 'actual': actual})
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--register', type=Path, default=Path('docs/research/claims/claim_evidence.csv'))
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    register = pd.read_csv(args.register)
    outcomes = verify(register, args.root)
    print(json.dumps({'claims': len(outcomes), 'regenerated': sum(o['status'] == 'regenerated' for o in outcomes),
                      'documented': sum(o['status'] == 'documented' for o in outcomes),
                      'pending': sum(o['status'] == 'pending' for o in outcomes)}, indent=2))


if __name__ == '__main__':
    main()
