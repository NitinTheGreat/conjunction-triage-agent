"""Explicit visible raw fields and retrospective versus decision-time cohorts."""
from __future__ import annotations
import numpy as np
import pandas as pd

OD_FIELDS = tuple(f'{role}_{name}' for role in ('t', 'c') for name in (
    'obs_available', 'obs_used', 'actual_od_span', 'recommended_od_span',
    'residuals_accepted', 'weighted_rms'))
AGE_FIELDS = tuple(f'{role}_time_lastob_{edge}' for role in ('t', 'c') for edge in ('end', 'start'))
RAW_FIELDS = ('risk', 'time_to_tca', 'miss_distance', 'relative_speed',
              *(f'{r}_sigma_{axis}' for r in ('t', 'c') for axis in ('r', 't', 'n')),
              *OD_FIELDS, *AGE_FIELDS)


def visible_records(frame: pd.DataFrame, cutoff: float = 2.0) -> pd.DataFrame:
    """Allowlist fields before any model transformation; labels never pass through."""
    missing = set(('series_id', *RAW_FIELDS)) - set(frame.columns)
    if missing:
        raise ValueError(f'Missing source columns: {sorted(missing)}')
    out = frame.loc[frame.time_to_tca >= cutoff, ['series_id', *RAW_FIELDS]].copy()
    if not np.isfinite(out[['risk', 'time_to_tca']].to_numpy(dtype=float)).all():
        raise ValueError('Non-finite visible time/risk requires an unresolved input record')
    # Tie ordering is content-based, not dependent on physical row order.
    return out.sort_values(['series_id', 'time_to_tca', *[c for c in RAW_FIELDS if c != 'time_to_tca']],
                           ascending=[True, False] + [True] * (len(RAW_FIELDS) - 1),
                           na_position='last', kind='stable').reset_index(drop=True)


def prospective_membership(frame: pd.DataFrame, cutoff: float = 2.0) -> set[str]:
    """Future availability or label changes cannot affect decision-time inclusion."""
    return set(frame.loc[(frame.time_to_tca >= cutoff) & np.isfinite(frame.risk), 'series_id'])


def lineage() -> dict:
    fields = {}
    for name in RAW_FIELDS:
        if name == 'risk': unit = 'log10 reported Pc'
        elif name == 'time_to_tca' or 'span' in name: unit = 'days'
        elif 'time_lastob' in name: unit = 'categorical interval code; signed/edge semantics unresolved'
        elif name == 'relative_speed': unit = 'm/s'
        elif 'sigma_' in name or name == 'miss_distance': unit = 'm'
        elif 'obs_' in name: unit = 'count'
        elif 'residuals_accepted' in name: unit = 'percent (provider field)'
        else: unit = 'provider normalized RMS'
        fields[name] = {'source': name, 'unit': unit, 'available_at': 'visible CDM',
                        'provenance_status': 'proxy' if name in OD_FIELDS + AGE_FIELDS else 'observed',
                        'missing': 'retained; training-only imputation with indicator'}
    return {'version': 1, 'cutoff_days': 2, 'fields': fields,
            'lineage_ground_truth': False, 'age_policy': 'categorical code plus unknown, never midpoint',
            'documentation': 'dataset/kelvins/raw_data_2015-2019.txt',
            'known_limits': ['Equal OD fields do not prove shared observations.',
                            'Relative TCA is not an absolute creation/arrival timestamp.']}
