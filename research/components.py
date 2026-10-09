"""Classifier-feature ablations and a separately labelled visible-lineage oracle."""
from __future__ import annotations

from dataclasses import dataclass
import json

import numpy as np

from research.data import OD_FIELDS, RAW_FIELDS, visible_records
from research.history import Event, HistoryTransformer, PHI_NAMES, events_from_frame, phi
from research.state_fusion import visible_union

ARMS = ('grouped_no_age', 'grouped_no_od_readout', 'fixed_no_od', 'oracle_lineage_weight')
AVAILABILITY = np.r_[np.linspace(8., 6.1, 60), np.linspace(1., .1, 20)]


@dataclass
class LineageEvent(Event):
    windows: tuple[tuple[int, ...], ...]


def kept_columns(arm):
    """Drop complete phi blocks: latest, mean, variance and missing fraction."""
    d = len(PHI_NAMES)
    if arm == 'grouped_no_age':
        removed = {i for i, name in enumerate(PHI_NAMES) if '_age_' in name}
    elif arm in ('grouped_no_od_readout', 'fixed_no_od'):
        removed = {PHI_NAMES.index(name) for name in OD_FIELDS}
    elif arm == 'oracle_lineage_weight':
        removed = set()
    else:
        raise ValueError(arm)
    drops = {offset+i for offset in (0, d, 2*d, 3*d+2) for i in removed}
    return np.array([i for i in range(4*d+2) if i not in drops], dtype=int)


def lineage_weights(windows):
    """Allocate each unique visible observation equally among containing messages."""
    union = visible_union(windows)
    multiplicity = np.zeros(60, dtype=int)
    for window in windows:
        multiplicity[np.asarray(window, dtype=int)] += 1
    weights = np.array([np.sum(1./multiplicity[np.asarray(w, dtype=int)])/len(union) for w in windows])
    # Mathematically equal allocations must reproduce the archived singleton.
    if np.ptp(weights) <= 1e-14:
        weights = np.full(len(windows), 1./len(windows))
    if not np.isfinite(weights).all() or np.any(weights <= 0) or not np.isclose(weights.sum(), 1., rtol=0, atol=1e-12):
        raise ValueError('Invalid oracle allocation')
    return weights


def lineage_events(messages, lineage, ids):
    """One condition at a time; canonicalize full visible records before joining."""
    raw_events = events_from_frame(visible_records(messages), ids)
    visible = lineage[lineage.available_at_tca_days >= 2.]
    groups = dict(tuple(visible.groupby('series_id', sort=False)))
    result = []
    for event in raw_events:
        if event.identity not in groups:
            raise ValueError('Missing lineage for visible event')
        entries = groups[event.identity].sort_values('message_index')
        if len(entries) != len(event.raw) or not np.array_equal(entries.message_index, np.arange(len(event.raw))):
            raise ValueError('Canonical lineage order/cardinality mismatch')
        windows = []
        for j, entry in enumerate(entries.itertuples(index=False)):
            ids_for_message = json.loads(entry.observation_ids)
            visible_union([ids_for_message])
            time = event.raw[j, RAW_FIELDS.index('time_to_tca')]
            if not np.isclose(time, entry.available_at_tca_days, atol=1e-12, rtol=0):
                raise ValueError('Lineage publication time mismatch')
            if not np.all(AVAILABILITY[ids_for_message] >= time):
                raise ValueError('Observation unavailable at publication')
            if entry.source_solution_id != ','.join(map(str, ids_for_message)):
                raise ValueError('Source solution identity mismatch')
            windows.append(tuple(ids_for_message))
        result.append(LineageEvent(event.identity, event.raw, tuple(windows)))
    return result


class ComponentTransformer:
    """Reuse archived preprocessing/families; change only named readout/weights."""
    def __init__(self, arm):
        self.arm = arm
        self.columns = kept_columns(arm)
        mode = 'fixed' if arm == 'fixed_no_od' else ('singleton' if arm == 'oracle_lineage_weight' else 'grouped')
        self.base = HistoryTransformer(mode)

    def fit(self, events):
        # Event construction enforces full-record visibility/canonicalization.
        # Scaling is columnwise, so unused fitted columns cannot alter kept ones.
        self.check_prefixes(events)
        self.base.fit(events)
        return self

    @staticmethod
    def check_prefixes(events):
        for event in events:
            if not len(event.raw) or not np.isfinite(event.raw[:, :2]).all() or np.any(event.raw[:, 1] < 2.):
                raise ValueError('Expected a canonical visible prefix with finite risk/time')

    def transform(self, events):
        self.check_prefixes(events)
        design, owners, objective_weights = self.base.transform(events)
        if self.arm == 'oracle_lineage_weight':
            values = phi(np.concatenate([e.raw for e in events]))
            all_z = self.base.scaler.transform(self.base.imputer.transform(values))
            offset, d = 0, len(PHI_NAMES)
            for index, event in enumerate(events):
                if not isinstance(event, LineageEvent) or len(event.windows) != len(event.raw):
                    raise ValueError('Oracle requires one audited window per canonical message')
                w = lineage_weights(event.windows)
                z = all_z[offset:offset+len(event.raw)]; offset += len(event.raw)
                if np.array_equal(w, np.full(len(w), 1./len(w))):
                    continue  # Exact archived arithmetic for uniform allocation.
                mean = np.sum(z*w[:, None], axis=0)
                design[index, d:2*d] = mean
                design[index, 2*d:3*d] = np.sum((z-mean)**2*w[:, None], axis=0)
            # Latest, span, canonical message count and missingness stay unchanged.
        return design[:, self.columns], owners, objective_weights
