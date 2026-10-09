"""Label-free history representations with explicit unknown provenance."""
from __future__ import annotations
from dataclasses import dataclass
import hashlib

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

from research.data import RAW_FIELDS, OD_FIELDS, AGE_FIELDS

CONTINUOUS = tuple(c for c in RAW_FIELDS if c not in AGE_FIELDS)
PHI_NAMES = (*CONTINUOUS, *(f'{r}_age_{b}' for r in ('t', 'c') for b in ('0_1', '1_2', '2_180', 'unknown')))


@dataclass
class Event:
    identity: str
    raw: np.ndarray


def events_from_frame(frame: pd.DataFrame, ids: list[str]) -> list[Event]:
    groups = {str(s): g[list(RAW_FIELDS)].to_numpy(dtype=float) for s, g in frame.groupby('series_id', sort=False)}
    return [Event(s, canonicalize(groups[s])) for s in ids]


def canonicalize(raw: np.ndarray) -> np.ndarray:
    """Exact substantive-content retransmission only; source epoch is included."""
    if raw.ndim != 2 or raw.shape[1] != len(RAW_FIELDS) or not len(raw):
        raise ValueError('Expected nonempty allowlisted message matrix')
    if np.isinf(raw).any():
        raise ValueError('Infinite source fields require explicit unresolved-input handling')
    # NaNs sort last and identical missing-value patterns count as exact replay.
    comparable=np.where(np.isnan(raw),np.inf,raw)
    columns=[1,*[j for j in range(raw.shape[1]) if j!=1]]
    keys=[(-comparable[:,j] if j==1 else comparable[:,j]) for j in columns]
    order=np.lexsort(tuple(keys[::-1]))
    ordered=comparable[order]
    keep=np.r_[True,np.any(ordered[1:]!=ordered[:-1],axis=1)]
    return raw[order[keep]].copy()


def phi(raw: np.ndarray) -> np.ndarray:
    continuous = raw[:, [RAW_FIELDS.index(c) for c in CONTINUOUS]]
    ages = []
    for role in ('t','c'):
        a = raw[:,RAW_FIELDS.index(f'{role}_time_lastob_end')]
        b = raw[:,RAW_FIELDS.index(f'{role}_time_lastob_start')]
        bins = np.column_stack([np.isclose(a,x,rtol=0,atol=1e-8)&np.isclose(b,y,rtol=0,atol=1e-8)
                                for x,y in ((0,1),(1,2),(2,180))])
        ages.append(np.column_stack([bins,~bins.any(axis=1)]).astype(float))
    return np.column_stack([continuous,*ages])


def components(merge: np.ndarray) -> np.ndarray:
    return np.r_[0,np.cumsum(~merge)].astype(int)


def partitions(event: Event, scaled: np.ndarray, mode: str) -> list[np.ndarray]:
    n = len(event.raw)
    od_idx = [RAW_FIELDS.index(c) for c in OD_FIELDS]
    phi_od_idx = [PHI_NAMES.index(c) for c in OD_FIELDS]
    od = event.raw[:,od_idx]
    gap = event.raw[:-1,RAW_FIELDS.index('time_to_tca')]-event.raw[1:,RAW_FIELDS.index('time_to_tca')]
    known = np.isfinite(od[:-1]).all(axis=1)&np.isfinite(od[1:]).all(axis=1)
    equal = known & (od[:-1]==od[1:]).all(axis=1)
    distance = np.max(np.abs(scaled[:-1,phi_od_idx]-scaled[1:,phi_od_idx]),axis=1) if n>1 else np.array([])
    family = [np.arange(n),components(equal)]
    for distance_cap in (0.5,2.):
        for gap_cap in (0.25,1.):
            family.append(components(known & (distance<=distance_cap)&(gap<=gap_cap)))
    for unknown_cap in (0.25,1.):
        family.append(components((known&(distance<=0.5)&(gap<=0.25))|(~known&(gap<=unknown_cap))))
    if mode == 'singleton': family = [np.arange(n)]
    elif mode == 'fixed':
        family = [np.arange(n)] + [components(gap<=cap) for cap in (0.,0.125,0.25,0.5,1.,2.,4.)]
    elif mode == 'random':
        seed = int(hashlib.sha256(event.identity.encode()).hexdigest()[:16],16)
        rng = np.random.default_rng(seed)
        family = [rng.permutation(p) for p in family]
    elif mode != 'grouped': raise ValueError(mode)
    unique = {tuple(p.tolist()):p for p in family}
    return list(unique.values())


class HistoryTransformer:
    """Fit all imputation/scaling within the relevant training partition."""
    def __init__(self, mode='grouped'):
        self.mode = mode
        self.imputer = SimpleImputer(strategy='median',keep_empty_features=True)
        self.scaler = RobustScaler()

    def fit(self, events: list[Event]):
        values = phi(np.concatenate([e.raw for e in events]))
        self.imputer.fit(values)
        self.scaler.fit(self.imputer.transform(values))
        return self

    def transform(self, events: list[Event]):
        rows,owners,weights = [],[],[]
        prepared=[]
        for index,event in enumerate(events):
            raw = event.raw
            if self.mode == 'thin':
                # Keep latest, then messages >=6h apart, preserving actual source times.
                keep = [len(raw)-1]
                for j in range(len(raw)-2,-1,-1):
                    if raw[j,1]-raw[keep[-1],1]>=0.25:keep.append(j)
                raw = raw[sorted(keep)]
            elif self.mode == 'change':
                od = raw[:,[RAW_FIELDS.index(c) for c in OD_FIELDS]]
                keep = np.r_[np.any(od[:-1]!=od[1:],axis=1)|(raw[:-1,0]!=raw[1:,0]),True]
                raw = raw[keep]
            elif self.mode == 'ignore_updates':raw = raw[:1]
            elif self.mode == 'latest_metadata':raw = raw[-1:]
            prepared.append(Event(event.identity,raw))
        # sklearn transforms are row-wise: batching avoids tens of thousands of
        # repeated validation calls without changing fitting scope or arithmetic.
        combined=phi(np.concatenate([e.raw for e in prepared]))
        all_z=self.scaler.transform(self.imputer.transform(combined))
        offset=0
        for index,e in enumerate(prepared):
            raw=e.raw
            values=combined[offset:offset+len(raw)]
            z=all_z[offset:offset+len(raw)]
            offset+=len(raw)
            missing = (~np.isfinite(values)).mean(axis=0)
            family = partitions(e,z,self.mode) if self.mode in ('grouped','fixed','random','singleton') else [np.arange(len(raw))]
            if self.mode == 'latest_metadata':
                design = [np.r_[z[-1],missing]]
            else:
                design = []
                for group in family:
                    counts = np.bincount(group)
                    w = 1./(len(counts)*counts[group])
                    mean = np.sum(z*w[:,None],axis=0)
                    variance = np.sum((z-mean)**2*w[:,None],axis=0)
                    design.append(np.r_[z[-1],mean,variance,raw[0,1]-raw[-1,1],len(counts),missing])
            rows.extend(design); owners.extend([index]*len(design));weights.extend([1./len(design)]*len(design))
        return np.asarray(rows),np.asarray(owners),np.asarray(weights)
