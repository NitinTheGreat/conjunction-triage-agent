import numpy as np
import pandas as pd
from research.data import RAW_FIELDS
from research.history import Event,canonicalize,HistoryTransformer,partitions,phi
from research.models import MonotonePlatt,policy_threshold
from research.metrics import class_metrics,official_metrics


def event():
    values=np.ones((5,len(RAW_FIELDS)))
    values[:,0]=[-9.,-8.,-7.,-6.5,-6.]
    values[:,1]=[5.,4.,3.,2.5,2.]
    values[2,RAW_FIELDS.index('t_obs_used')]=np.nan
    return Event('example',canonicalize(values))


def test_all_history_controls_are_exact_replay_invariant():
    e=event()
    replay=Event(e.identity,canonicalize(np.concatenate([e.raw,e.raw[[1,2,1]]])[::-1]))
    for arm in ['grouped','singleton','fixed','random','thin','change','ignore_updates','latest_metadata']:
        transform=HistoryTransformer(arm).fit([e])
        a,owner,w=transform.transform([e]);b,_,wb=transform.transform([replay])
        np.testing.assert_array_equal(a,b)
        assert np.isclose(w.sum(),1) and np.isclose(wb.sum(),1)
        assert len(a)<=8 and (owner==0).all()


def test_partition_family_and_unknown_cases():
    e=event();transform=HistoryTransformer().fit([e])
    z=transform.scaler.transform(transform.imputer.transform(phi(e.raw)))
    family=partitions(e,z,'grouped')
    assert 1<=len(family)<=8
    assert len({tuple(p) for p in family})==len(family)
    assert any(len(set(p))==len(e.raw) for p in family)


def test_batched_history_transform_matches_separate_events_and_reference_order():
    e=event();other=Event('other',canonicalize(e.raw+0.1))
    noisy=np.concatenate([e.raw,e.raw[[1,2]]])[::-1]
    df=pd.DataFrame(noisy,columns=RAW_FIELDS).drop_duplicates()
    expected=df.sort_values(['time_to_tca',*[c for c in RAW_FIELDS if c!='time_to_tca']],
                            ascending=[False]+[True]*(len(RAW_FIELDS)-1),na_position='last').to_numpy(float)
    np.testing.assert_array_equal(canonicalize(noisy),expected)
    for arm in ('grouped','singleton','thin','latest_metadata'):
        transform=HistoryTransformer(arm).fit([e,other])
        batch,owner,weights=transform.transform([e,other])
        for i,item in enumerate([e,other]):
            one,_,w=transform.transform([item])
            np.testing.assert_allclose(batch[owner==i],one,rtol=0,atol=0)
            np.testing.assert_array_equal(weights[owner==i],w)


def test_calibration_and_recall_threshold_denominators():
    q=np.linspace(.01,.99,100); y=(q>.8).astype(int)
    cal=MonotonePlatt().fit(q,y)
    assert cal.slope>=0 and (np.diff(cal.predict(q))>=0).all()
    threshold=policy_threshold(q,y,.99)
    assert (q[y==1]>=threshold).mean()>=.99
    out=class_metrics(y,q,q>=threshold)
    assert out['positives']==20 and out['fn']==0
    empty=official_metrics(np.array([-9.,-8.]),np.array([-7.,-7.]))
    assert empty['metric_status']=='undefined_no_positives' and empty['L'] is None
