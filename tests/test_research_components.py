import json

import numpy as np
import pandas as pd
import pytest

from research.components import (ARMS, ComponentTransformer, LineageEvent,
    kept_columns, lineage_events, lineage_weights)
from research.data import AGE_FIELDS, OD_FIELDS, RAW_FIELDS, visible_records
from research.history import Event, HistoryTransformer, PHI_NAMES, canonicalize, events_from_frame, partitions, phi


def event(identity='x', times=(6., 5.9, 5.75, 3.5, 2.1, 2.)):
    raw = np.ones((len(times), len(RAW_FIELDS)))
    raw[:, 0] = np.linspace(-9, -5, len(times)); raw[:, 1] = times
    raw[:, 2] = np.arange(len(times))*10.
    for role in ('t', 'c'):
        raw[:, RAW_FIELDS.index(f'{role}_time_lastob_end')] = [0, 1, 2, 0, 1, np.nan][:len(times)]
        raw[:, RAW_FIELDS.index(f'{role}_time_lastob_start')] = [1, 2, 180, 1, 2, np.nan][:len(times)]
    return Event(identity, canonicalize(raw))


@pytest.mark.parametrize('arm,mode,width', [('grouped_no_age','grouped',90),
    ('grouped_no_od_readout','grouped',74), ('fixed_no_od','fixed',74)])
def test_removed_columns_and_retained_design_exactly_match_archived_base(arm,mode,width):
    events=[event()]
    expected=HistoryTransformer(mode).fit(events).transform(events)
    actual=ComponentTransformer(arm).fit(events).transform(events)
    assert actual[0].shape[1] == width
    np.testing.assert_array_equal(actual[0], expected[0][:,kept_columns(arm)])
    np.testing.assert_array_equal(actual[1],expected[1]);np.testing.assert_array_equal(actual[2],expected[2])
    assert np.bincount(actual[1],weights=actual[2])[0] == pytest.approx(1.)
    d=len(PHI_NAMES)
    fields=[i for i,n in enumerate(PHI_NAMES) if '_age_' in n] if arm=='grouped_no_age' else [PHI_NAMES.index(n) for n in OD_FIELDS]
    for offset in (0,d,2*d,3*d+2):
        assert not set(offset+i for i in fields)&set(kept_columns(arm))
    assert {3*d,3*d+1} <= set(kept_columns(arm))


def test_age_changes_never_change_groups_and_removed_age_cannot_change_readout():
    e=event(); changed=event();changed.raw[:,[RAW_FIELDS.index(n) for n in AGE_FIELDS]]=999.
    transform=ComponentTransformer('grouped_no_age').fit([e])
    for a,b in zip(transform.transform([e]),transform.transform([changed])):np.testing.assert_array_equal(a,b)
    base=HistoryTransformer('grouped').fit([e])
    assert not np.array_equal(base.transform([e])[0],base.transform([changed])[0])
    z=base.scaler.transform(base.imputer.transform(phi(e.raw)))
    assert [p.tolist() for p in partitions(e,z,'grouped')]==[p.tolist() for p in partitions(changed,z,'grouped')]


def test_od_readout_removal_retains_grouping_but_fixed_no_od_ignores_od_after_canonicalization():
    e=event();changed=event()
    for i,name in enumerate(OD_FIELDS):changed.raw[:,RAW_FIELDS.index(name)]=np.arange(6)*(10+i)
    for arm in ('grouped_no_od_readout','fixed_no_od'):
        t=ComponentTransformer(arm).fit([e]); a=t.transform([e]);b=t.transform([changed])
        if arm=='fixed_no_od':
            for x,y in zip(a,b):np.testing.assert_array_equal(x,y)
            # Fitting unused OD scales also cannot alter retained columns.
            for x,y in zip(a,ComponentTransformer(arm).fit([changed]).transform([changed])):np.testing.assert_array_equal(x,y)
        else:
            assert a[0].shape!=b[0].shape or not np.array_equal(a[0],b[0])


@pytest.mark.parametrize('windows,expected', [(((0,1),(2,3)),[.5,.5]),
    (((0,1),(0,1)),[.5,.5]), (((0,1),(0,1),(2,3)),[.25,.25,.5]),
    (((0,1),(1,2)),[.5,.5]), (((0,),(0,1)),[.25,.75])])
def test_oracle_allocations_analytic(windows,expected):
    np.testing.assert_allclose(lineage_weights(windows),expected,atol=1e-15,rtol=0)


@pytest.mark.parametrize('windows', [(), ((),), ((0,0),), ((-1,),), ((60,),), ((1.5,),), ((True,),)])
def test_oracle_rejects_invalid_or_future_observation_ids(windows):
    with pytest.raises(ValueError):lineage_weights(windows)


def lineage_fixture():
    e=event(times=(6.,4.,2.));windows=((0,1),(0,1,2),(0,1,2,3))
    messages=pd.DataFrame(e.raw,columns=RAW_FIELDS).assign(series_id='x')
    lineage=pd.DataFrame([{'series_id':'x','message_index':j,'observation_ids':json.dumps(w),
        'source_solution_id':','.join(map(str,w)),'available_at_tca_days':e.raw[j,1]} for j,w in enumerate(windows)])
    return messages,lineage


def test_lineage_join_canonical_replay_future_exclusion_and_order_validation():
    messages,lineage=lineage_fixture()
    expected=lineage_events(messages,lineage,['x'])[0]
    future=messages.iloc[-1:].copy();future.time_to_tca=.5;future.risk=999.
    later=lineage.iloc[-1:].copy();later.available_at_tca_days=.5;later.message_index=3;later.observation_ids='[60, 79]'
    altered=pd.concat([messages.iloc[::-1],messages,future]).assign(final_risk=123,oracle_hidden=1)
    actual=lineage_events(altered,pd.concat([lineage,later]),['x'])[0]
    np.testing.assert_array_equal(actual.raw,expected.raw);assert actual.windows==expected.windows
    for arm in ARMS:
        t=ComponentTransformer(arm).fit([expected]);state=t.base.imputer.statistics_.copy()
        for x,y in zip(t.transform([expected]),t.transform([actual])):np.testing.assert_array_equal(x,y)
        np.testing.assert_array_equal(state,t.base.imputer.statistics_)
    invalid=lineage.copy();invalid.loc[0,'available_at_tca_days']=5.9
    with pytest.raises(ValueError,match='publication time'):lineage_events(messages,invalid,['x'])
    invalid=lineage.copy();invalid.loc[0,'message_index']=1
    with pytest.raises(ValueError,match='order/cardinality'):lineage_events(messages,invalid,['x'])


def test_oracle_only_changes_mean_variance_and_uniform_exactly_equals_singleton():
    messages,lineage=lineage_fixture();e=lineage_events(messages,lineage,['x'])[0]
    base=HistoryTransformer('singleton').fit([e]).transform([e])
    actual=ComponentTransformer('oracle_lineage_weight').fit([e]).transform([e])
    d=len(PHI_NAMES)
    retained=np.r_[np.arange(d),np.arange(3*d,4*d+2)]
    np.testing.assert_array_equal(actual[0][:,retained],base[0][:,retained])
    assert not np.array_equal(actual[0][:,d:3*d],base[0][:,d:3*d])
    for windows in (((0,1),(2,3),(4,5)),((0,1),(0,1),(0,1))):
        uniform=LineageEvent(e.identity,e.raw,windows)
        result=ComponentTransformer('oracle_lineage_weight').fit([uniform]).transform([uniform])
        for a,b in zip(result,base):np.testing.assert_array_equal(a,b)


def test_ordinary_components_ignore_oracle_windows_and_preprocessor_never_refits_on_prediction():
    messages,lineage=lineage_fixture();e=lineage_events(messages,lineage,['x'])[0]
    changed=LineageEvent('renamed',e.raw,((60,),(60,),(60,)))
    for arm in ARMS[:-1]:
        t=ComponentTransformer(arm).fit([e]);state=t.base.scaler.center_.copy()
        for a,b in zip(t.transform([e]),t.transform([changed])):np.testing.assert_array_equal(a,b)
        np.testing.assert_array_equal(t.base.scaler.center_,state)
    e.raw[0,1]=.5
    with pytest.raises(ValueError,match='visible prefix'):ComponentTransformer('grouped_no_age').fit([e])
